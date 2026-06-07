from django.contrib import admin
from django.core.exceptions import ValidationError
from .models import (
    Literature,
    PlaceName,
    PlaceNameLiterature,
    NameRelation,
    CollationNote,
    Dispute,
    MigrationRecord,
    MigrationStage,
    MigrationEvidence,
    MigrationDispute,
    MigrationVersion,
)


class PlaceNameLiteratureInline(admin.TabularInline):
    model = PlaceNameLiterature
    extra = 1
    verbose_name = '文献出处'
    verbose_name_plural = '文献出处'


class CollationNoteInline(admin.TabularInline):
    model = CollationNote
    extra = 0
    fields = ('title', 'collator', 'collation_date', 'conclusion')
    readonly_fields = ('created_at',)
    verbose_name = '校勘意见'
    verbose_name_plural = '校勘意见'


class DisputeInline(admin.TabularInline):
    model = Dispute
    extra = 0
    fields = ('title', 'proposer', 'status', 'resolution')
    readonly_fields = ('created_at',)
    verbose_name = '争议记录'
    verbose_name_plural = '争议记录'


@admin.register(Literature)
class LiteratureAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'dynasty', 'volume', 'page')
    search_fields = ('title', 'author', 'dynasty')
    list_filter = ('dynasty',)


@admin.register(PlaceName)
class PlaceNameAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'alternative_name',
        'region',
        'start_year',
        'end_year',
        'reliability',
        'collation_status',
        'has_literature',
        'has_unresolved_disputes',
    )
    search_fields = ('name', 'alternative_name', 'region')
    list_filter = (
        'region',
        'collation_status',
        'reliability',
    )
    inlines = [
        PlaceNameLiteratureInline,
        CollationNoteInline,
        DisputeInline,
    ]
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('基本信息', {
            'fields': (
                'name',
                'alternative_name',
                'region',
                'description',
            )
        }),
        ('年代信息', {
            'fields': (
                'start_year',
                'end_year',
            )
        }),
        ('位置信息', {
            'fields': (
                'longitude',
                'latitude',
            ),
            'classes': ('collapse',),
        }),
        ('校勘信息', {
            'fields': (
                'reliability',
                'collation_status',
            )
        }),
        ('系统信息', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',),
        }),
    )

    def has_literature(self, obj):
        return obj.literatures.exists()
    has_literature.boolean = True
    has_literature.short_description = '有文献出处'

    def has_unresolved_disputes(self, obj):
        return obj.has_unresolved_disputes()
    has_unresolved_disputes.boolean = True
    has_unresolved_disputes.short_description = '有未解决争议'

    def save_model(self, request, obj, form, change):
        if not change:
            obj.save()
        else:
            super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        obj = form.instance
        if not obj.literatures.exists():
            raise ValidationError('地名记录不能缺少文献出处，请至少添加一条文献出处。')


@admin.register(NameRelation)
class NameRelationAdmin(admin.ModelAdmin):
    list_display = (
        'name_a',
        'name_b',
        'relation_type',
        'reliability',
        'confirmed',
        'created_at',
    )
    list_filter = (
        'relation_type',
        'confirmed',
        'reliability',
    )
    search_fields = (
        'name_a__name',
        'name_b__name',
        'description',
    )
    readonly_fields = ('created_at', 'updated_at')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name in ['name_a', 'name_b']:
            kwargs['queryset'] = PlaceName.objects.order_by('name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(CollationNote)
class CollationNoteAdmin(admin.ModelAdmin):
    list_display = (
        'place_name',
        'title',
        'collator',
        'collation_date',
    )
    list_filter = ('collation_date', 'collator')
    search_fields = (
        'place_name__name',
        'title',
        'content',
        'conclusion',
    )
    date_hierarchy = 'collation_date'
    readonly_fields = ('created_at',)


@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display = (
        'place_name',
        'title',
        'proposer',
        'status',
        'created_at',
        'resolved_date',
    )
    list_filter = ('status', 'created_at')
    search_fields = (
        'place_name__name',
        'title',
        'content',
        'proposer',
    )
    readonly_fields = ('created_at',)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)


class MigrationStageInline(admin.TabularInline):
    model = MigrationStage
    extra = 1
    fields = ('stage_name', 'dynasty', 'start_year', 'end_year', 'administrative_division', 'order_index')
    verbose_name = '迁移阶段'
    verbose_name_plural = '迁移阶段'


class MigrationEvidenceInline(admin.TabularInline):
    model = MigrationEvidence
    extra = 1
    fields = ('literature', 'evidence_type', 'reliability', 'citation_detail')
    verbose_name = '文献证据'
    verbose_name_plural = '文献证据'


class MigrationDisputeInline(admin.TabularInline):
    model = MigrationDispute
    extra = 0
    fields = ('title', 'proposer', 'status', 'stage')
    readonly_fields = ('created_at',)
    verbose_name = '迁移争议'
    verbose_name_plural = '迁移争议'


@admin.register(MigrationRecord)
class MigrationRecordAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'place_name',
        'migration_type',
        'dynasty',
        'region',
        'reliability',
        'status',
        'has_disputes',
    )
    search_fields = ('title', 'place_name__name', 'region')
    list_filter = ('migration_type', 'dynasty', 'region', 'reliability', 'status')
    inlines = [
        MigrationStageInline,
        MigrationEvidenceInline,
        MigrationDisputeInline,
    ]
    readonly_fields = ('created_at', 'updated_at')

    def has_disputes(self, obj):
        return obj.disputes.filter(status__in=['open', 'investigating']).exists()
    has_disputes.boolean = True
    has_disputes.short_description = '有未解决争议'


@admin.register(MigrationStage)
class MigrationStageAdmin(admin.ModelAdmin):
    list_display = (
        'migration_record',
        'stage_name',
        'dynasty',
        'place_name_text',
        'administrative_division',
        'reliability',
        'order_index',
    )
    list_filter = ('dynasty', 'region', 'reliability')
    search_fields = ('migration_record__title', 'stage_name', 'place_name_text', 'administrative_division')
    readonly_fields = ('created_at',)


@admin.register(MigrationEvidence)
class MigrationEvidenceAdmin(admin.ModelAdmin):
    list_display = (
        'migration_record',
        'stage',
        'literature',
        'evidence_type',
        'reliability',
        'citation_detail',
    )
    list_filter = ('evidence_type', 'reliability')
    search_fields = ('migration_record__title', 'literature__title', 'citation_detail', 'evidence_content')


@admin.register(MigrationDispute)
class MigrationDisputeAdmin(admin.ModelAdmin):
    list_display = (
        'migration_record',
        'title',
        'stage',
        'proposer',
        'status',
        'created_at',
        'resolved_date',
    )
    list_filter = ('status', 'created_at')
    search_fields = ('migration_record__title', 'title', 'content', 'proposer')
    readonly_fields = ('created_at',)


@admin.register(MigrationVersion)
class MigrationVersionAdmin(admin.ModelAdmin):
    list_display = (
        'migration_record',
        'version_number',
        'created_at',
        'change_fields_display',
    )
    list_filter = ('created_at',)
    search_fields = ('migration_record__title', 'change_fields', 'change_summary')
    readonly_fields = ('created_at',)

    def change_fields_display(self, obj):
        fields = obj.change_fields
        if fields and len(fields) > 0:
            return ', '.join(fields[:3]) + ('...' if len(fields) > 3 else '')
        return '-'
    change_fields_display.short_description = '变更字段'
