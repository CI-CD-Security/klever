#
# Copyright (c) 2014-2016 ISPRAS (http://www.ispras.ru)
# Institute for System Programming of the Russian Academy of Sciences
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import re

from core.vtg.emg.grammars.process import parse_process


def generate_regex_set(subprocess_name):
    dispatch_template = '\[@?{}(?:\[[^)]+\])?\]'
    receive_template = '\(!?{}(?:\[[^)]+\])?\)'
    condition_template = '<{}(?:\[[^)]+\])?>'
    subprocess_template = '{}'

    subprocess_re = re.compile('\{' + subprocess_template.format(subprocess_name) + '\}')
    receive_re = re.compile(receive_template.format(subprocess_name))
    dispatch_re = re.compile(dispatch_template.format(subprocess_name))
    condition_template_re = re.compile(condition_template.format(subprocess_name))
    regexes = [
        {'regex': subprocess_re, 'type': Subprocess},
        {'regex': dispatch_re, 'type': Dispatch},
        {'regex': receive_re, 'type': Receive},
        {'regex': condition_template_re, 'type': Condition}
    ]

    return regexes


def _update_process_ast(obj):
    obj.__process_ast = parse_process(obj.process)


def export_process(process):
    def convert_label(label):
        d = dict()
        d['signature'] = label.prior_signature.to_string(label.name, typedef='complex_and_params')
        if label.value:
            d['value'] = label.value

        return d

    def convert_action(action):
        d = dict()
        if action.comment:
            d['comment'] = action.comment
        if action.condition:
            d['condition'] = action.condition

        if isinstance(action, Subprocess):
            d['process'] = action.process
        elif isinstance(action, Dispatch) or isinstance(action, Receive):
            d['parameters'] = action.parameters

            if len(action.peers) > 0:
                d['peers'] = [p['process'].external_id for p in action.peers]

            if isinstance(action, Dispatch) and action.broadcast:
                d['broadcast'] = action.broadcast
            elif isinstance(action, Receive) and action.replicative:
                d['replicative'] = action.replicative
        elif isinstance(action, Condition):
            if action.statements:
                d["statements"] = action.statements

        return d

    data = {
        'identifier': process.external_id,
        'comment': process.comment,
        'process': process.process,
        'labels': {l.name: convert_label(l) for l in process.labels.values()},
        'actions': {a.name: convert_action(a) for a in process.actions.values()}
    }
    if len(process.headers) > 0:
        data['headers'] = list(process.headers)
    if len(process.declarations.keys()) > 0:
        data['declarations'] = process.declarations
    if len(process.definitions.keys()) > 0:
        data['definitions'] = process.definitions

    return data


class Access:
    def __init__(self, expression):
        self.expression = expression
        self.label = None
        self.list_access = None


class Label:

    def __init__(self, name):
        self.value = None
        self.prior_signature = None
        self.name = name

    def compare_with(self, label):
        if self.prior_signature and label.prior_signature:
            my_signature = self.prior_signature
            ret = my_signature.compare_signature(label.prior_signature)
            if not ret:
                return 'different'
            else:
                return 'equal'
        else:
            raise NotImplementedError("Cannot compare label '{}' with label '{}'".format(label.name, label.name))


class Process:
    label_re = re.compile('%(\w+)((?:\.\w*)*)%')

    def __init__(self, name):
        self.name = name
        self.category = None
        self.identifier = None
        self.comment = None
        self.labels = {}
        self.actions = {}
        self.process = None
        self.headers = list()
        self.declarations = dict()
        self.definitions = dict()
        self.external_id = None
        self._process_ast = None
        self._accesses = dict()

    @property
    def unmatched_receives(self):
        return [self.actions[act] for act in sorted(self.actions.keys()) if isinstance(self.actions[act], Receive) and
                len(self.actions[act].peers) == 0]

    @property
    def unmatched_dispatches(self):
        return [self.actions[act] for act in sorted(self.actions.keys()) if isinstance(self.actions[act], Dispatch) and
                len(self.actions[act].peers) == 0]

    @property
    def process_ast(self):
        if not self._process_ast:
            self._process_ast = parse_process(self.process)
        return self._process_ast

    def insert_action(self, old, new, position):
        if not old or old not in self.actions:
            raise KeyError('Cannot rename action {!r} in process {!r} because it does not exist'.
                           format(old, self.name))
        if position == 'instead':
            # Delete old subprocess
            del self.actions[old]

        # Replace action entries
        processes = [self]
        processes.extend(
            [self.actions[name] for name in sorted(self.actions.keys()) if isinstance(self.actions[name], Subprocess)])
        regexes = generate_regex_set(old)
        for process in processes:
            for regex in regexes:
                m = regex['regex'].search(process.process)
                if m:
                    # Replace signal entries
                    curr_expr = m.group(0)
                    if position == 'before':
                        next_expr = "{}.{}".format(new, curr_expr)
                    elif position == 'after':
                        next_expr = "{}.{}".format(curr_expr, new)
                    elif position == 'instead':
                        next_expr = new
                    else:
                        next_expr = '({} | {})'.format(curr_expr, new)

                    process.process = process.process.replace(curr_expr, next_expr)
                    break
            process.update_process_ast()

    def rename_action(self, name, new_name):
        if name not in self.actions:
            raise KeyError('Cannot rename subprocess {} in process {} because it does not exist'.
                           format(name, self.name))

        action = self.actions[name]
        action.name = new_name

        # Delete old subprocess
        del self.actions[name]

        # Set new subprocess
        self.actions[action.name] = action

        # Replace subprocess entries
        processes = [self]
        processes.extend(
            [self.actions[name] for name in sorted(self.actions.keys()) if isinstance(self.actions[name], Subprocess)])
        regexes = generate_regex_set(name)
        for process in processes:
            for regex in regexes:
                if regex['regex'].search(process.process):
                    # Replace signal entries
                    old_match = regex['regex'].search(process.process).group()
                    new_match = old_match.replace(name, new_name)
                    process.process = process.process.replace(old_match, new_match)
            process.update_process_ast()

    def resolve_access(self, access):
        if isinstance(access, Label):
            string = '%{}%'.format(access.name)
        elif isinstance(access, str):
            string = access
        else:
            raise TypeError('Unsupported access token')
        return self._accesses[string]

    def update_process_ast(self):
        _update_process_ast(self)

    def add_declaration(self, file, name, string):
        if file not in self.declarations:
            self.declarations[file] = dict()

        if name not in self.declarations:
            self.declarations[file][name] = string

    def add_definition(self, file, name, strings):
        if file not in self.definitions:
            self.definitions[file] = dict()

        if name not in self.definitions:
            self.definitions[file][name] = strings


class Action:

    def __init__(self, name):
        self.name = name
        self.comment = None
        self.condition = None


class Subprocess(Action):

    def __init__(self, name):
        super().__init__(name)
        self.process = None
        self.__process_ast = None

    @property
    def process_ast(self):
        if not self.__process_ast:
            self.__process_ast = parse_process(self.process)
        return self.__process_ast

    def update_process_ast(self):
        _update_process_ast(self)


class Dispatch(Action):

    def __init__(self, name):
        super().__init__(name)
        self.parameters = []
        self.broadcast = False
        self.peers = []


class Receive(Action):

    def __init__(self, name):
        super().__init__(name)
        self.parameters = []
        self.replicative = False
        self.peers = []


class Condition(Action):

    def __init__(self, name):
        super().__init__(name)
        self.statements = []
