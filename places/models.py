import json
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone


class Literature(models.Model):
    title = models.CharField('书名/文献名', max_length=200)
    author = models.CharField('作者', max_length=100, blank=True)
    dynasty = models.CharField('朝代/年代', max_length=100, blank=True)
    publisher = models.CharField('出版地/出版社', max_length=200, blank=True)
    volume = models.CharField('卷/册', max_length=50, blank=True)
    page = models.CharField('页码/篇目', max_length=50, blank=True)
    note = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '文献出处'
        verbose_name_plural = '文献出处'
        ordering = ['title']

    def __str__(self):
        parts = [self.title]
        if self.author:
            parts.append(f'（{self.author}）')
        if self.dynasty:
            parts.append(f'[{self.dynasty}]')
        if self.volume or self.page:
            loc = []
            if self.volume:
                loc.append(f'卷{self.volume}')
            if self.page:
                loc.append(f'第{self.page}页')
            parts.append('，'.join(loc))
        return ''.join(parts)

    def get_cited_places(self):
        return PlaceName.objects.filter(
            placenameliterature__literature=self
        ).distinct()

    def get_citation_chain(self, depth=3):
        visited = set()
        chain = []
        self._traverse_citations(self, visited, chain, 0, depth)
        return chain

    def _traverse_citations(self, lit, visited, chain, current_depth, max_depth):
        if current_depth >= max_depth or lit.id in visited:
            return
        visited.add(lit.id)
        chain.append({'literature': lit, 'depth': current_depth})
        for place in lit.get_cited_places():
            for lit_rel in place.placenameliterature_set.select_related('literature'):
                if lit_rel.literature.id != lit.id:
                    self._traverse_citations(
                        lit_rel.literature, visited, chain,
                        current_depth + 1, max_depth
                    )


class PlaceName(models.Model):
    COLLATION_STATUS_CHOICES = [
        ('pending', '未校勘'),
        ('in_progress', '校勘中'),
        ('completed', '已完成'),
    ]

    REVIEW_STATUS_CHOICES = [
        ('draft', '草稿'),
        ('submitted', '待审核'),
        ('reviewing', '审核中'),
        ('approved', '已通过'),
        ('rejected', '已驳回'),
        ('archived', '已归档'),
    ]

    name = models.CharField('地名', max_length=100)
    alternative_name = models.CharField('别名/简称', max_length=100, blank=True)
    region = models.CharField('所属地区', max_length=200, blank=True)
    start_year = models.CharField('始见年代', max_length=50, blank=True)
    end_year = models.CharField('废止年代', max_length=50, blank=True)
    start_year_num = models.IntegerField('始见年(数值)', null=True, blank=True)
    end_year_num = models.IntegerField('废止年(数值)', null=True, blank=True)
    reliability = models.IntegerField('可信度', default=50)
    description = models.TextField('地名描述', blank=True)
    collation_status = models.CharField(
        '校勘状态',
        max_length=20,
        choices=COLLATION_STATUS_CHOICES,
        default='pending'
    )
    review_status = models.CharField(
        '审核状态',
        max_length=20,
        choices=REVIEW_STATUS_CHOICES,
        default='draft'
    )
    submitter = models.CharField('提交人', max_length=100, blank=True)
    submitted_at = models.DateTimeField('提交时间', null=True, blank=True)
    reviewer = models.CharField('审核人', max_length=100, blank=True)
    reviewed_at = models.DateTimeField('审核时间', null=True, blank=True)
    review_comment = models.TextField('审核意见', blank=True)
    longitude = models.FloatField('经度', null=True, blank=True)
    latitude = models.FloatField('纬度', null=True, blank=True)
    literatures = models.ManyToManyField(
        Literature,
        through='PlaceNameLiterature',
        verbose_name='文献出处'
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '古地名'
        verbose_name_plural = '古地名'
        ordering = ['name']

    def __str__(self):
        return self.name

    def clean(self):
        if self.reliability < 0 or self.reliability > 100:
            raise ValidationError({'reliability': '可信度必须在 0-100 之间'})

        if self.pk and self.collation_status == 'completed':
            if self.has_unresolved_disputes():
                raise ValidationError({
                    'collation_status': '存在未解决争议时不能标记为校勘完成'
                })

        if self.start_year_num is not None and self.end_year_num is not None:
            if self.start_year_num > self.end_year_num:
                raise ValidationError({
                    'start_year_num': '始见年不能晚于废止年'
                })

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_instance = None
        if not is_new:
            old_instance = PlaceName.objects.filter(pk=self.pk).first()

        self.full_clean()
        super().save(*args, **kwargs)

        if not is_new and old_instance:
            self._create_version_if_changed(old_instance)

    def _create_version_if_changed(self, old_instance):
        fields_to_track = [
            'name', 'alternative_name', 'region', 'start_year', 'end_year',
            'start_year_num', 'end_year_num', 'reliability', 'description',
            'longitude', 'latitude'
        ]
        changes = {}
        for field in fields_to_track:
            old_val = getattr(old_instance, field)
            new_val = getattr(self, field)
            if old_val != new_val:
                changes[field] = {
                    'old': str(old_val) if old_val is not None else '',
                    'new': str(new_val) if new_val is not None else '',
                }
        if changes:
            latest_version = PlaceNameVersion.objects.filter(
                place_name=self
            ).order_by('-version_number').first()
            version_num = latest_version.version_number + 1 if latest_version else 1
            PlaceNameVersion.objects.create(
                place_name=self,
                version_number=version_num,
                change_summary=json.dumps(changes, ensure_ascii=False),
                change_fields=list(changes.keys()),
            )

    def has_unresolved_disputes(self):
        return self.disputes.filter(status='open').exists()

    def get_all_related_names(self):
        relations = NameRelation.objects.filter(
            models.Q(name_a=self) | models.Q(name_b=self),
            confirmed=True
        ).select_related('name_a', 'name_b')
        related = set()
        for rel in relations:
            if rel.name_a == self:
                related.add(rel.name_b)
            else:
                related.add(rel.name_a)
        return related

    def can_delete(self):
        has_relations = NameRelation.objects.filter(
            models.Q(name_a=self) | models.Q(name_b=self)
        ).exists()
        has_notes = self.collation_notes.exists()
        has_disputes = self.disputes.exists()
        has_versions = self.versions.exists()
        has_annotations = Annotation.objects.filter(
            target_type='place', target_id=self.pk
        ).exists()
        has_pending_deletion = DeletionRequest.objects.filter(
            place_name=self, status__in=['pending', 'reviewing']
        ).exists()
        return not (has_relations or has_notes or has_disputes or has_versions
                    or has_annotations or has_pending_deletion)

    def delete_with_check(self):
        if not self.can_delete():
            raise ValidationError('该地名存在关联关系、校勘意见或争议记录，无法删除')
        self.delete()

    def submit_for_review(self, submitter=''):
        if self.review_status not in ['draft', 'rejected']:
            raise ValidationError('当前状态不允许提交审核')
        if not self.placenameliterature_set.exists():
            raise ValidationError('提交审核前必须至少关联一条文献出处')
        self.review_status = 'submitted'
        self.submitter = submitter
        self.submitted_at = timezone.now()
        self.save(update_fields=['review_status', 'submitter', 'submitted_at'])

    def approve(self, reviewer='', comment=''):
        if self.review_status not in ['submitted', 'reviewing']:
            raise ValidationError('当前状态不允许审核通过')
        self.review_status = 'approved'
        self.reviewer = reviewer
        self.reviewed_at = timezone.now()
        self.review_comment = comment
        self.collation_status = 'in_progress'
        self.save(update_fields=[
            'review_status', 'reviewer', 'reviewed_at',
            'review_comment', 'collation_status'
        ])

    def reject(self, reviewer='', comment=''):
        if self.review_status not in ['submitted', 'reviewing']:
            raise ValidationError('当前状态不允许驳回')
        if not comment:
            raise ValidationError('驳回时必须填写审核意见')
        self.review_status = 'rejected'
        self.reviewer = reviewer
        self.reviewed_at = timezone.now()
        self.review_comment = comment
        self.save(update_fields=[
            'review_status', 'reviewer', 'reviewed_at', 'review_comment'
        ])

    def archive(self):
        if self.review_status != 'approved' or self.collation_status != 'completed':
            raise ValidationError('只有已通过审核且校勘完成的地名才能归档')
        if self.has_unresolved_disputes():
            raise ValidationError('存在未解决争议时不能归档')
        self.review_status = 'archived'
        self.save(update_fields=['review_status'])


class PlaceNameVersion(models.Model):
    place_name = models.ForeignKey(
        PlaceName,
        on_delete=models.CASCADE,
        related_name='versions',
        verbose_name='地名'
    )
    version_number = models.IntegerField('版本号', default=1)
    change_summary = models.TextField('变更摘要', default='{}')
    change_fields = models.JSONField('变更字段', default=list)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '地名版本'
        verbose_name_plural = '地名版本'
        ordering = ['-version_number']
        unique_together = ('place_name', 'version_number')

    def __str__(self):
        return f'{self.place_name.name} - v{self.version_number}'

    def get_changes_dict(self):
        try:
            return json.loads(self.change_summary)
        except (json.JSONDecodeError, TypeError):
            return {}


class PlaceNameLiterature(models.Model):
    place_name = models.ForeignKey(PlaceName, on_delete=models.CASCADE, verbose_name='地名')
    literature = models.ForeignKey(Literature, on_delete=models.CASCADE, verbose_name='文献出处')
    citation_detail = models.CharField('引用细节', max_length=200, blank=True)

    class Meta:
        verbose_name = '地名-文献关联'
        verbose_name_plural = '地名-文献关联'
        unique_together = ('place_name', 'literature')

    def __str__(self):
        return f'{self.place_name.name} - {self.literature.title}'


class NameRelation(models.Model):
    RELATION_TYPE_CHOICES = [
        ('alias', '异名'),
        ('error', '讹误'),
        ('evolution', '沿革'),
        ('belong_to', '隶属'),
        ('other', '其他'),
    ]

    STATUS_CHOICES = [
        ('proposed', '待确认'),
        ('confirmed', '已确认'),
        ('disputed', '有争议'),
        ('rejected', '已驳回'),
    ]

    name_a = models.ForeignKey(
        PlaceName,
        on_delete=models.CASCADE,
        related_name='relations_as_a',
        verbose_name='地名A'
    )
    name_b = models.ForeignKey(
        PlaceName,
        on_delete=models.CASCADE,
        related_name='relations_as_b',
        verbose_name='地名B'
    )
    relation_type = models.CharField(
        '关系类型',
        max_length=20,
        choices=RELATION_TYPE_CHOICES,
        default='alias'
    )
    reliability = models.IntegerField('可信度', default=50)
    confirmed = models.BooleanField('是否已确认', default=False)
    status = models.CharField(
        '关系状态',
        max_length=20,
        choices=STATUS_CHOICES,
        default='proposed'
    )
    description = models.TextField('关系说明', blank=True)
    proposer = models.CharField('提出人', max_length=100, blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '异名关系'
        verbose_name_plural = '异名关系'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name_a.name} ↔ {self.name_b.name}（{self.get_relation_type_display()}）'

    def clean(self):
        if self.name_a_id == self.name_b_id:
            raise ValidationError('同一名称不能关联到自身')

        if self.reliability < 0 or self.reliability > 100:
            raise ValidationError({'reliability': '可信度必须在 0-100 之间'})

        if self.status == 'confirmed' and self.pk is None:
            existing = NameRelation.objects.filter(
                models.Q(name_a=self.name_a, name_b=self.name_b) |
                models.Q(name_a=self.name_b, name_b=self.name_a),
                status='confirmed'
            ).exists()
            if existing:
                raise ValidationError('已确认的异名关系不能重复创建')

    def save(self, *args, **kwargs):
        if self.status == 'confirmed':
            self.confirmed = True
        else:
            self.confirmed = False
        self.full_clean()
        super().save(*args, **kwargs)

    def get_other_name(self, current_name):
        if current_name == self.name_a:
            return self.name_b
        return self.name_a


class CollationNote(models.Model):
    place_name = models.ForeignKey(
        PlaceName,
        on_delete=models.CASCADE,
        related_name='collation_notes',
        verbose_name='地名'
    )
    title = models.CharField('意见标题', max_length=200)
    content = models.TextField('校勘内容')
    conclusion = models.TextField('校勘结论', blank=True)
    collator = models.CharField('校勘人', max_length=100, blank=True)
    collation_date = models.DateField('校勘日期', default=timezone.now)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '校勘意见'
        verbose_name_plural = '校勘意见'
        ordering = ['-collation_date']

    def __str__(self):
        return f'{self.place_name.name} - {self.title}'


class Dispute(models.Model):
    STATUS_CHOICES = [
        ('open', '处理中'),
        ('investigating', '调查中'),
        ('resolved', '已解决'),
        ('rejected', '已驳回'),
        ('closed', '已关闭'),
    ]

    RESOLUTION_TYPE_CHOICES = [
        ('', '未解决'),
        ('evidence', '证据裁定'),
        ('vote', '投票表决'),
        ('expert', '专家裁定'),
        ('merged', '合并处理'),
        ('withdrawn', '撤回申请'),
    ]

    place_name = models.ForeignKey(
        PlaceName,
        on_delete=models.CASCADE,
        related_name='disputes',
        verbose_name='地名'
    )
    title = models.CharField('争议标题', max_length=200)
    content = models.TextField('争议内容')
    proposer = models.CharField('提出者', max_length=100, blank=True)
    status = models.CharField(
        '状态',
        max_length=20,
        choices=STATUS_CHOICES,
        default='open'
    )
    resolution_type = models.CharField(
        '解决方式',
        max_length=20,
        choices=RESOLUTION_TYPE_CHOICES,
        default='',
        blank=True
    )
    resolution = models.TextField('解决方案', blank=True)
    resolver = models.CharField('处理人', max_length=100, blank=True)
    resolved_date = models.DateField('解决日期', null=True, blank=True)
    reopen_count = models.IntegerField('重新开启次数', default=0)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '争议记录'
        verbose_name_plural = '争议记录'
        ordering = ['-created_at']

    def __str__(self):
        status_text = self.get_status_display()
        return f'[{status_text}] {self.place_name.name} - {self.title}'

    def save(self, *args, **kwargs):
        if self.status in ['resolved', 'rejected', 'closed'] and not self.resolved_date:
            self.resolved_date = timezone.now().date()
        if self.status in ['open', 'investigating']:
            self.resolved_date = None
        super().save(*args, **kwargs)
        self._update_place_collation_status()

    def _update_place_collation_status(self):
        place = self.place_name
        has_open = place.disputes.filter(status__in=['open', 'investigating']).exists()
        if has_open:
            if place.collation_status == 'completed':
                place.collation_status = 'in_progress'
                place.save(update_fields=['collation_status'])

    def resolve(self, resolver='', resolution='', resolution_type='evidence'):
        if self.status not in ['open', 'investigating']:
            raise ValidationError('当前状态不允许解决')
        if not resolution:
            raise ValidationError('解决争议时必须填写解决方案')
        self.status = 'resolved'
        self.resolution_type = resolution_type
        self.resolution = resolution
        self.resolver = resolver
        self.save()

    def reject_dispute(self, resolver='', reason=''):
        if self.status not in ['open', 'investigating']:
            raise ValidationError('当前状态不允许驳回')
        if not reason:
            raise ValidationError('驳回争议时必须填写理由')
        self.status = 'rejected'
        self.resolution = reason
        self.resolver = resolver
        self.save()

    def reopen(self, reopener='', reason=''):
        if self.status not in ['resolved', 'rejected', 'closed']:
            raise ValidationError('当前状态不允许重新开启')
        self.status = 'open'
        self.reopen_count += 1
        self.resolved_date = None
        self.save()


class ReviewRecord(models.Model):
    ACTION_CHOICES = [
        ('submit', '提交审核'),
        ('approve', '审核通过'),
        ('reject', '审核驳回'),
        ('archive', '归档'),
        ('reopen', '重新提交'),
    ]

    place_name = models.ForeignKey(
        PlaceName,
        on_delete=models.CASCADE,
        related_name='review_records',
        verbose_name='地名',
        null=True,
        blank=True
    )
    relation = models.ForeignKey(
        NameRelation,
        on_delete=models.CASCADE,
        related_name='review_records',
        verbose_name='关系',
        null=True,
        blank=True
    )
    action = models.CharField('操作类型', max_length=20, choices=ACTION_CHOICES)
    operator = models.CharField('操作人', max_length=100, blank=True)
    comment = models.TextField('审核意见', blank=True)
    created_at = models.DateTimeField('操作时间', auto_now_add=True)

    class Meta:
        verbose_name = '审核记录'
        verbose_name_plural = '审核记录'
        ordering = ['-created_at']

    def __str__(self):
        target = self.place_name.name if self.place_name else (
            str(self.relation) if self.relation else '未知'
        )
        return f'[{self.get_action_display()}] {target}'


class DeletionRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', '待审核'),
        ('reviewing', '审核中'),
        ('approved', '已批准'),
        ('rejected', '已驳回'),
        ('completed', '已完成'),
        ('cancelled', '已取消'),
    ]

    place_name = models.ForeignKey(
        PlaceName,
        on_delete=models.SET_NULL,
        null=True,
        related_name='deletion_requests',
        verbose_name='地名'
    )
    place_name_snapshot = models.CharField('地名快照', max_length=200, blank=True)
    reason = models.TextField('删除理由')
    applicant = models.CharField('申请人', max_length=100, blank=True)
    status = models.CharField(
        '状态',
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    reviewer = models.CharField('审核人', max_length=100, blank=True)
    review_comment = models.TextField('审核意见', blank=True)
    reviewed_at = models.DateTimeField('审核时间', null=True, blank=True)
    executed_at = models.DateTimeField('执行时间', null=True, blank=True)
    created_at = models.DateTimeField('申请时间', auto_now_add=True)

    class Meta:
        verbose_name = '删除申请'
        verbose_name_plural = '删除申请'
        ordering = ['-created_at']

    def __str__(self):
        name = self.place_name_snapshot or (self.place_name.name if self.place_name else '未知')
        return f'{name} - 删除申请'

    def clean(self):
        if self.pk is None:
            existing = DeletionRequest.objects.filter(
                place_name=self.place_name,
                status__in=['pending', 'reviewing']
            ).exists()
            if existing:
                raise ValidationError('该地名已有待审核的删除申请')

    def save(self, *args, **kwargs):
        if self.place_name and not self.place_name_snapshot:
            self.place_name_snapshot = self.place_name.name
        self.full_clean()
        super().save(*args, **kwargs)

    def approve(self, reviewer='', comment=''):
        if self.status not in ['pending', 'reviewing']:
            raise ValidationError('当前状态不允许批准')
        self.status = 'approved'
        self.reviewer = reviewer
        self.review_comment = comment
        self.reviewed_at = timezone.now()
        self.save()

    def reject(self, reviewer='', comment=''):
        if self.status not in ['pending', 'reviewing']:
            raise ValidationError('当前状态不允许驳回')
        if not comment:
            raise ValidationError('驳回删除申请时必须填写理由')
        self.status = 'rejected'
        self.reviewer = reviewer
        self.review_comment = comment
        self.reviewed_at = timezone.now()
        self.save()

    def execute(self):
        if self.status != 'approved':
            raise ValidationError('只有已批准的删除申请才能执行')
        if self.place_name:
            place_name_str = self.place_name.name
            place_pk = self.place_name.pk
            if not self.place_name_snapshot:
                self.place_name_snapshot = place_name_str
            PlaceName.objects.filter(pk=place_pk).delete()
            DeletionRequest.objects.filter(pk=self.pk).update(
                status='completed',
                executed_at=timezone.now(),
                place_name=None,
                place_name_snapshot=self.place_name_snapshot,
            )
            self.status = 'completed'
            self.executed_at = timezone.now()
            self.place_name = None
        else:
            place_name_str = self.place_name_snapshot
            DeletionRequest.objects.filter(pk=self.pk).update(
                status='completed',
                executed_at=timezone.now(),
            )
            self.status = 'completed'
            self.executed_at = timezone.now()
        return place_name_str

    def cancel(self):
        if self.status not in ['pending', 'reviewing']:
            raise ValidationError('当前状态不允许取消')
        self.status = 'cancelled'
        self.save()


class Annotation(models.Model):
    TARGET_TYPE_CHOICES = [
        ('place', '地名'),
        ('relation', '关系'),
        ('literature', '文献'),
        ('collation', '校勘意见'),
        ('dispute', '争议记录'),
    ]

    target_type = models.CharField('目标类型', max_length=20, choices=TARGET_TYPE_CHOICES)
    target_id = models.IntegerField('目标ID')
    content = models.TextField('批注内容')
    author = models.CharField('批注人', max_length=100, blank=True)
    reply_to = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        related_name='replies',
        null=True,
        blank=True,
        verbose_name='回复给'
    )
    is_resolved = models.BooleanField('是否已解决', default=False)
    resolved_by = models.CharField('解决人', max_length=100, blank=True)
    resolved_at = models.DateTimeField('解决时间', null=True, blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '协作批注'
        verbose_name_plural = '协作批注'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_target_type_display()}批注 - {self.content[:30]}'

    def resolve(self, resolver=''):
        if self.is_resolved:
            raise ValidationError('该批注已被解决')
        self.is_resolved = True
        self.resolved_by = resolver
        self.resolved_at = timezone.now()
        self.save()


class MigrationRecord(models.Model):
    MIGRATION_TYPE_CHOICES = [
        ('administrative', '行政变迁'),
        ('geographic', '地理迁移'),
        ('name_change', '名称变更'),
        ('boundary_change', '边界变动'),
        ('merge', '合并'),
        ('split', '拆分'),
        ('other', '其他'),
    ]

    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('submitted', '待审核'),
        ('approved', '已通过'),
        ('rejected', '已驳回'),
    ]

    place_name = models.ForeignKey(
        PlaceName,
        on_delete=models.CASCADE,
        related_name='migrations',
        verbose_name='关联地名'
    )
    title = models.CharField('迁移标题', max_length=200)
    migration_type = models.CharField(
        '迁移类型',
        max_length=20,
        choices=MIGRATION_TYPE_CHOICES,
        default='administrative'
    )
    region = models.CharField('所属地区', max_length=200, blank=True)
    dynasty = models.CharField('朝代/年代', max_length=100, blank=True)
    start_year = models.CharField('起始年代', max_length=50, blank=True)
    end_year = models.CharField('结束年代', max_length=50, blank=True)
    start_year_num = models.IntegerField('起始年(数值)', null=True, blank=True)
    end_year_num = models.IntegerField('结束年(数值)', null=True, blank=True)
    reliability = models.IntegerField('可信度', default=50)
    migration_reason = models.TextField('迁移原因', blank=True)
    conclusion = models.TextField('迁移结论', blank=True)
    has_dispute = models.BooleanField('存在争议', default=False)
    status = models.CharField(
        '状态',
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )
    submitter = models.CharField('提交人', max_length=100, blank=True)
    submitted_at = models.DateTimeField('提交时间', null=True, blank=True)
    reviewer = models.CharField('审核人', max_length=100, blank=True)
    reviewed_at = models.DateTimeField('审核时间', null=True, blank=True)
    review_comment = models.TextField('审核意见', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '时空迁移对照'
        verbose_name_plural = '时空迁移对照'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.place_name.name} - {self.title}'

    def clean(self):
        if self.reliability < 0 or self.reliability > 100:
            raise ValidationError({'reliability': '可信度必须在 0-100 之间'})
        if self.start_year_num is not None and self.end_year_num is not None:
            if self.start_year_num > self.end_year_num:
                raise ValidationError({
                    'start_year_num': '起始年不能晚于结束年'
                })

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_instance = None
        if not is_new:
            old_instance = MigrationRecord.objects.filter(pk=self.pk).first()

        self.full_clean()
        super().save(*args, **kwargs)

        if not is_new and old_instance:
            self._create_version_if_changed(old_instance)

    def _create_version_if_changed(self, old_instance):
        fields_to_track = [
            'title', 'migration_type', 'region', 'dynasty',
            'start_year', 'end_year', 'start_year_num', 'end_year_num',
            'reliability', 'migration_reason', 'conclusion', 'has_dispute'
        ]
        changes = {}
        for field in fields_to_track:
            old_val = getattr(old_instance, field)
            new_val = getattr(self, field)
            if old_val != new_val:
                changes[field] = {
                    'old': str(old_val) if old_val is not None else '',
                    'new': str(new_val) if new_val is not None else '',
                }
        if changes:
            latest_version = MigrationVersion.objects.filter(
                migration_record=self
            ).order_by('-version_number').first()
            version_num = latest_version.version_number + 1 if latest_version else 1
            MigrationVersion.objects.create(
                migration_record=self,
                version_number=version_num,
                change_summary=json.dumps(changes, ensure_ascii=False),
                change_fields=list(changes.keys()),
            )

    def get_stages_sorted(self):
        return self.stages.order_by('start_year_num', 'start_year')

    def submit_for_review(self, submitter=''):
        if self.status not in ['draft', 'rejected']:
            raise ValidationError('当前状态不允许提交审核')
        if not self.stages.exists():
            raise ValidationError('提交审核前必须至少添加一个迁移阶段')
        self.status = 'submitted'
        self.submitter = submitter
        self.submitted_at = timezone.now()
        self.save(update_fields=['status', 'submitter', 'submitted_at'])

    def approve(self, reviewer='', comment=''):
        if self.status not in ['submitted']:
            raise ValidationError('当前状态不允许审核通过')
        self.status = 'approved'
        self.reviewer = reviewer
        self.reviewed_at = timezone.now()
        self.review_comment = comment
        self.save(update_fields=[
            'status', 'reviewer', 'reviewed_at', 'review_comment'
        ])

    def reject(self, reviewer='', comment=''):
        if self.status not in ['submitted']:
            raise ValidationError('当前状态不允许驳回')
        if not comment:
            raise ValidationError('驳回时必须填写审核意见')
        self.status = 'rejected'
        self.reviewer = reviewer
        self.reviewed_at = timezone.now()
        self.review_comment = comment
        self.save(update_fields=[
            'status', 'reviewer', 'reviewed_at', 'review_comment'
        ])


class MigrationStage(models.Model):
    migration_record = models.ForeignKey(
        MigrationRecord,
        on_delete=models.CASCADE,
        related_name='stages',
        verbose_name='迁移记录'
    )
    stage_name = models.CharField('阶段名称', max_length=200)
    dynasty = models.CharField('朝代/时期', max_length=100, blank=True)
    start_year = models.CharField('起始年代', max_length=50, blank=True)
    end_year = models.CharField('结束年代', max_length=50, blank=True)
    start_year_num = models.IntegerField('起始年(数值)', null=True, blank=True)
    end_year_num = models.IntegerField('结束年(数值)', null=True, blank=True)
    place_name_text = models.CharField('当时地名', max_length=100, blank=True)
    administrative_division = models.CharField('行政隶属', max_length=200, blank=True)
    region = models.CharField('所属地区', max_length=200, blank=True)
    longitude = models.FloatField('经度', null=True, blank=True)
    latitude = models.FloatField('纬度', null=True, blank=True)
    coordinate_range = models.TextField('坐标范围/四至', blank=True)
    description = models.TextField('地理描述', blank=True)
    evidence = models.TextField('证据说明', blank=True)
    reliability = models.IntegerField('可信度', default=50)
    order_index = models.IntegerField('排序', default=0)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '迁移阶段'
        verbose_name_plural = '迁移阶段'
        ordering = ['order_index', 'start_year_num', 'start_year']

    def __str__(self):
        return f'{self.stage_name}（{self.start_year}-{self.end_year}）'

    def clean(self):
        if self.reliability < 0 or self.reliability > 100:
            raise ValidationError({'reliability': '可信度必须在 0-100 之间'})


class MigrationEvidence(models.Model):
    migration_record = models.ForeignKey(
        MigrationRecord,
        on_delete=models.CASCADE,
        related_name='evidences',
        verbose_name='迁移记录'
    )
    stage = models.ForeignKey(
        MigrationStage,
        on_delete=models.SET_NULL,
        related_name='evidences',
        verbose_name='关联阶段',
        null=True,
        blank=True
    )
    literature = models.ForeignKey(
        Literature,
        on_delete=models.CASCADE,
        related_name='migration_evidences',
        verbose_name='文献出处'
    )
    citation_detail = models.CharField('引用细节', max_length=200, blank=True)
    evidence_content = models.TextField('证据内容', blank=True)
    evidence_type = models.CharField('证据类型', max_length=50, blank=True)
    reliability = models.IntegerField('证据可信度', default=50)
    order_index = models.IntegerField('排序', default=0)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '迁移证据'
        verbose_name_plural = '迁移证据'
        ordering = ['order_index', 'created_at']

    def __str__(self):
        return f'{self.literature.title} - {self.citation_detail}'

    def clean(self):
        if self.reliability < 0 or self.reliability > 100:
            raise ValidationError({'reliability': '可信度必须在 0-100 之间'})


class MigrationDispute(models.Model):
    STATUS_CHOICES = [
        ('open', '处理中'),
        ('investigating', '调查中'),
        ('resolved', '已解决'),
        ('rejected', '已驳回'),
        ('closed', '已关闭'),
    ]

    migration_record = models.ForeignKey(
        MigrationRecord,
        on_delete=models.CASCADE,
        related_name='disputes',
        verbose_name='迁移记录'
    )
    stage = models.ForeignKey(
        MigrationStage,
        on_delete=models.SET_NULL,
        related_name='disputes',
        verbose_name='关联阶段',
        null=True,
        blank=True
    )
    title = models.CharField('争议标题', max_length=200)
    content = models.TextField('争议内容')
    proposer = models.CharField('提出者', max_length=100, blank=True)
    status = models.CharField(
        '状态',
        max_length=20,
        choices=STATUS_CHOICES,
        default='open'
    )
    resolution = models.TextField('解决方案', blank=True)
    resolver = models.CharField('处理人', max_length=100, blank=True)
    resolved_date = models.DateField('解决日期', null=True, blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '迁移争议'
        verbose_name_plural = '迁移争议'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.get_status_display()}] {self.title}'

    def save(self, *args, **kwargs):
        if self.status in ['resolved', 'rejected', 'closed'] and not self.resolved_date:
            self.resolved_date = timezone.now().date()
        if self.status in ['open', 'investigating']:
            self.resolved_date = None
        super().save(*args, **kwargs)
        self._update_migration_dispute_status()

    def _update_migration_dispute_status(self):
        record = self.migration_record
        has_open = record.disputes.filter(
            status__in=['open', 'investigating']
        ).exists()
        if has_open != record.has_dispute:
            record.has_dispute = has_open
            record.save(update_fields=['has_dispute'])


class MigrationVersion(models.Model):
    migration_record = models.ForeignKey(
        MigrationRecord,
        on_delete=models.CASCADE,
        related_name='versions',
        verbose_name='迁移记录'
    )
    version_number = models.IntegerField('版本号', default=1)
    change_summary = models.TextField('变更摘要', default='{}')
    change_fields = models.JSONField('变更字段', default=list)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '迁移版本'
        verbose_name_plural = '迁移版本'
        ordering = ['-version_number']
        unique_together = ('migration_record', 'version_number')

    def __str__(self):
        return f'{self.migration_record.title} - v{self.version_number}'

    def get_changes_dict(self):
        try:
            return json.loads(self.change_summary)
        except (json.JSONDecodeError, TypeError):
            return {}


class OperationLog(models.Model):
    ACTION_CHOICES = [
        ('create', '创建'),
        ('update', '更新'),
        ('delete', '删除'),
        ('submit', '提交'),
        ('approve', '通过'),
        ('reject', '驳回'),
        ('resolve', '解决'),
        ('archive', '归档'),
        ('other', '其他'),
    ]

    TARGET_TYPE_CHOICES = [
        ('place', '地名'),
        ('relation', '关系'),
        ('literature', '文献'),
        ('collation', '校勘意见'),
        ('dispute', '争议记录'),
        ('annotation', '批注'),
        ('deletion_request', '删除申请'),
        ('review', '审核记录'),
        ('migration', '迁移对照'),
    ]

    target_type = models.CharField('目标类型', max_length=30, choices=TARGET_TYPE_CHOICES)
    target_id = models.IntegerField('目标ID', null=True, blank=True)
    target_name = models.CharField('目标名称', max_length=200, blank=True)
    action = models.CharField('操作类型', max_length=20, choices=ACTION_CHOICES)
    operator = models.CharField('操作人', max_length=100, blank=True)
    detail = models.TextField('操作详情', blank=True)
    ip_address = models.GenericIPAddressField('IP地址', null=True, blank=True)
    created_at = models.DateTimeField('操作时间', auto_now_add=True)

    class Meta:
        verbose_name = '操作日志'
        verbose_name_plural = '操作日志'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.get_action_display()}] {self.get_target_type_display()}: {self.target_name}'

    @classmethod
    def log(cls, target_type, target_id, action, target_name='',
            operator='', detail='', ip_address=None):
        return cls.objects.create(
            target_type=target_type,
            target_id=target_id,
            target_name=target_name,
            action=action,
            operator=operator,
            detail=detail,
            ip_address=ip_address,
        )
