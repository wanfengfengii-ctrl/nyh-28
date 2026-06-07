from django.contrib import admin
from django.core.exceptions import ValidationError
from .models import (
    Literature,
    PlaceName,
    PlaceNameLiterature,
    NameRelation,
    CollationNote,
    Dispute,
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
