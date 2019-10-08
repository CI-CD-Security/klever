from collections import OrderedDict, Mapping
from django.db.models import F, Count, Case, When, BooleanField
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

from rest_framework import serializers, fields, exceptions

from bridge.vars import ASSOCIATION_TYPE, SAFE_VERDICTS, UNSAFE_VERDICTS
from bridge.serializers import TimeStampField

from jobs.models import Job
from reports.models import (
    ReportRoot, ReportSafe, ReportUnsafe, ReportUnknown, ReportAttr, ReportComponent, Computer,
    OriginalSources
)
from marks.models import (
    MarkSafeReport, MarkUnsafeReport, MarkUnknownReport, MarkSafeHistory, MarkUnsafeHistory, MarkUnknownHistory
)


class VerdictsSerializerRO(serializers.ModelSerializer):
    safes = fields.SerializerMethodField()
    unsafes = fields.SerializerMethodField()
    unknowns = fields.SerializerMethodField()

    def __verdicts_data(self, queryset):
        data = list(queryset.values('cache__verdict').annotate(
            total=Count('id'), verdict=F('cache__verdict'),
            confirmed=Count(Case(When(cache__marks_confirmed__gt=0, then=1)))
        ).order_by('verdict').values('verdict', 'total', 'confirmed'))
        data.append({
            'verdict': 'total',
            'total': sum(x['total'] for x in data),
            'confirmed': sum(x['confirmed'] for x in data)
        })
        return data

    def get_safes(self, instance):
        return self.__verdicts_data(ReportSafe.objects.filter(root=instance).select_related('cache'))

    def get_unsafes(self, instance):
        return self.__verdicts_data(ReportUnsafe.objects.filter(root=instance).select_related('cache'))

    def get_unknowns(self, instance):
        unknowns_data = {}

        # Marked/Unmarked unknowns
        unconfirmed_annotation = Case(
            When(markreport_set__type=ASSOCIATION_TYPE[2][0], then=True),
            default=False, output_field=BooleanField()
        )
        queryset = ReportUnknown.objects.filter(root=instance) \
            .values('component', 'markreport_set__problem') \
            .annotate(number=Count('id', distinct=True), unconfirmed=unconfirmed_annotation) \
            .values_list('component', 'markreport_set__problem', 'number', 'unconfirmed')
        for component, problem, number, unconfirmed in queryset:
            data_key = (component, 'Without marks' if problem is None or unconfirmed else problem)
            unknowns_data.setdefault(data_key, 0)
            unknowns_data[data_key] += number
        unknowns_list = list({
            'component': component, 'problem': problem,
            'number': unknowns_data[component, problem]
        } for component, problem in sorted(unknowns_data))

        # Total unknowns for each component
        queryset = ReportUnknown.objects.filter(root=instance) \
            .values('component').annotate(number=Count('id')) \
            .values_list('component', 'number').order_by('component')
        totals_list = list({'component': component, 'problem': 'Total', 'number': number}
                           for component, number in queryset)
        return unknowns_list + totals_list

    class Meta:
        model = ReportRoot
        fields = ('safes', 'unsafes', 'unknowns')


class DecisionResultsSerializerRO(serializers.ModelSerializer):
    start_date = TimeStampField(required=False, source='decision.start_date')
    finish_date = TimeStampField(required=False, source='decision.finish_date')
    verdicts = serializers.SerializerMethodField()
    safes = fields.SerializerMethodField()
    unsafes = fields.SerializerMethodField()
    unknowns = fields.SerializerMethodField()

    def get_start_date(self, instance):
        start_date = instance.decision.start_date
        return start_date.timestamp() if start_date else None

    def get_finish_date(self, instance):
        finish_date = instance.decision.finish_date
        return finish_date.timestamp() if finish_date else None

    def get_verdicts(self, instance):
        return VerdictsSerializerRO(instance=instance.reportroot).data

    @cached_property
    def _attrs(self):
        if not self.instance:
            return {}
        queryset = ReportAttr.objects.filter(report__root=self.instance.reportroot).exclude(
            report__reportsafe=None, report__reportunsafe=None, report__reportunknown=None
        ).order_by('name').only('report_id', 'name', 'value')

        data = {}
        for attr in queryset:
            data.setdefault(attr.report_id, [])
            data[attr.report_id].append([attr.name, attr.value])
        return data

    def get_safes(self, instance):
        reportroot = instance.reportroot
        marks = {}
        marks_ids = []
        reports = {}

        # Add reports with marks and their marks
        for mr in MarkSafeReport.objects.filter(report__root=reportroot).select_related('mark'):
            mark_identifier = str(mr.mark.identifier)
            if mr.report_id not in reports:
                reports[mr.report_id] = {
                    'attrs': self._attrs.get(mr.report_id, []),
                    'marks': [mark_identifier]
                }
            else:
                reports[mr.report_id]['marks'].append(mark_identifier)

            if mark_identifier not in marks:
                marks_ids.append(mr.mark_id)
                marks[mark_identifier] = {
                    'verdict': mr.mark.verdict,
                    'tags': mr.mark.cache_tags
                }

        # Collect marks descriptions
        history_qs = MarkSafeHistory.objects.filter(version=F('mark__version'), mark_id__in=marks_ids) \
            .select_related('mark').only('mark__identifier', 'description')
        for mark_version in history_qs:
            marks[str(mark_version.mark.identifier)]['description'] = mark_version.description

        # Add reports without marks
        for s_id in ReportSafe.objects.filter(root=reportroot, cache__verdict=SAFE_VERDICTS[4][0]) \
                .values_list('id', flat=True):
            reports[s_id] = {'attrs': self._attrs.get(s_id, []), 'marks': []}

        return {'marks': marks, 'reports': list(reports[r_id] for r_id in sorted(reports))}

    def get_unsafes(self, instance):
        reportroot = instance.reportroot
        marks = {}
        marks_ids = []
        reports = {}

        # Add reports with marks and their marks
        for mr in MarkUnsafeReport.objects.filter(report__root=reportroot).select_related('mark'):
            mark_identifier = str(mr.mark.identifier)
            if mr.report_id not in reports:
                reports[mr.report_id] = {
                    'attrs': self._attrs.get(mr.report_id, []),
                    'marks': {mark_identifier: mr.result}
                }
            else:
                reports[mr.report_id]['marks'][mark_identifier] = mr.result

            if mark_identifier not in marks:
                marks_ids.append(mr.mark_id)
                marks[mark_identifier] = {
                    'verdict': mr.mark.verdict,
                    'status': mr.mark.status,
                    'tags': mr.mark.cache_tags
                }

        # Collect marks descriptions
        history_qs = MarkUnsafeHistory.objects.filter(version=F('mark__version'), mark_id__in=marks_ids) \
            .select_related('mark').only('mark__identifier', 'description')
        for mark_version in history_qs:
            marks[str(mark_version.mark.identifier)]['description'] = mark_version.description

        # Add reports without marks
        for u_id in ReportUnsafe.objects.filter(root=reportroot, cache__verdict=UNSAFE_VERDICTS[5][0]) \
                .values_list('id', flat=True):
            reports[u_id] = {'attrs': self._attrs.get(u_id, []), 'marks': {}}

        return {'marks': marks, 'reports': list(reports[r_id] for r_id in sorted(reports))}

    def get_unknowns(self, instance):
        reportroot = instance.reportroot
        marks = {}
        marks_ids = []
        reports = {}

        # Get reports with marks and their marks
        for mr in MarkUnknownReport.objects.filter(report__root=reportroot).select_related('mark'):
            mark_identifier = str(mr.mark.identifier)
            if mr.report_id in reports:
                reports[mr.report_id]['marks'].append(mark_identifier)
            else:
                reports[mr.report_id] = {
                    'attrs': self._attrs.get(mr.report_id, []),
                    'marks': [mark_identifier]
                }

            if mark_identifier not in marks:
                marks_ids.append(mr.mark_id)
                marks[mark_identifier] = {
                    'component': mr.mark.component, 'function': mr.mark.function,
                    'is_regexp': mr.mark.is_regexp, 'problem_pattern': mr.mark.problem_pattern
                }

        # Collect marks descriptions
        history_qs = MarkUnknownHistory.objects.filter(version=F('mark__version'), mark_id__in=marks_ids) \
            .select_related('mark').only('mark__identifier', 'description')
        for mark_version in history_qs:
            marks[str(mark_version.mark.identifier)]['description'] = mark_version.description

        # Get reports without marks
        for f_id in ReportUnknown.objects.filter(root=reportroot).exclude(id__in=reports).values_list('id', flat=True):
            reports[f_id] = {'attrs': self._attrs.get(f_id, []), 'marks': []}

        return {'marks': marks, 'reports': list(reports[r_id] for r_id in sorted(reports))}

    class Meta:
        model = Job
        fields = ('name', 'status', 'start_date', 'finish_date', 'verdicts', 'safes', 'unsafes', 'unknowns')


class ComputerDataField(fields.Field):
    initial = []
    default_error_messages = {
        'not_a_list': _('Expected a list of items but got type "{input_type}".'),
        'prop_wrong': _('Computer property has wrong format.'),
    }

    def get_value(self, dictionary):
        if self.field_name not in dictionary:
            if getattr(self.root, 'partial', False):
                return fields.empty
        if fields.html.is_html_input(dictionary):
            val = dictionary.getlist(self.field_name, [])
            if len(val) > 0:
                return val
            return fields.html.parse_html_list(dictionary, prefix=self.field_name, default=fields.empty)
        return dictionary.get(self.field_name, fields.empty)

    def to_internal_value(self, data):
        if fields.html.is_html_input(data):
            data = fields.html.parse_html_list(data, default=[])
        if isinstance(data, str) or isinstance(data, Mapping) or not hasattr(data, '__iter__'):
            self.fail('not_a_list', input_type=type(data).__name__)
        return self.run_child_validation(data)

    def to_representation(self, data):
        return data

    def __validate_property(self, prop):
        if not isinstance(prop, dict) or len(prop) != 1:
            self.fail('prop_wrong')
        prop_key = next(iter(prop))
        prop_value = prop[prop_key]
        if not isinstance(prop_value, (str, int)):
            self.fail('prop_wrong')
        return [prop_key, prop_value]

    def run_child_validation(self, data):
        result = []
        errors = OrderedDict()
        for idx, item in enumerate(data):
            try:
                result.append(self.__validate_property(item))
            except exceptions.ValidationError as e:
                errors[idx] = e.detail
        if not errors:
            return result
        raise exceptions.ValidationError(errors)


class ComputerSerializer(serializers.ModelSerializer):
    data = ComputerDataField()

    def create(self, validated_data):
        try:
            # Do not create the computer with the same identifier again
            return Computer.objects.get(identifier=validated_data['identifier'])
        except Computer.DoesNotExist:
            return super().create(validated_data)

    class Meta:
        model = Computer
        fields = '__all__'


class ReportComponentSerializer(serializers.ModelSerializer):
    parent = serializers.SlugRelatedField(slug_field='identifier', allow_null=True, queryset=ReportComponent.objects)

    def create(self, validated_data):
        # Root, computer, parent must be specified in save() method
        assert 'root' in validated_data, _('Report root is required')
        assert 'computer' in validated_data, _('Report computer is required')
        assert 'parent' in validated_data, _('Report parent is required')

        return super().create(validated_data)

    class Meta:
        model = ReportComponent
        exclude = ('root', 'computer', 'parent')
        # parent, identifier, cpu_time, wall_time, memory,
        # start_date, finish_date, log, verifier_input, data


class ReportAttrSerializer(serializers.ModelSerializer):
    data_id = fields.IntegerField(allow_null=True, required=False)

    class Meta:
        model = ReportAttr
        fields = ('name', 'value', 'compare', 'associate', 'data_id')


class OriginalSourcesSerializer(serializers.ModelSerializer):
    class Meta:
        model = OriginalSources
        fields = '__all__'
