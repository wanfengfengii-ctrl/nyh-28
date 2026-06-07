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


class PlaceName(models.Model):
    COLLATION_STATUS_CHOICES = [
        ('pending', '未校勘'),
        ('in_progress', '校勘中'),
        ('completed', '已完成'),
    ]

    name = models.CharField('地名', max_length=100)
    alternative_name = models.CharField('别名/简称', max_length=100, blank=True)
    region = models.CharField('所属地区', max_length=200, blank=True)
    start_year = models.CharField('始见年代', max_length=50, blank=True)
    end_year = models.CharField('废止年代', max_length=50, blank=True)
    reliability = models.IntegerField('可信度', default=50)
    description = models.TextField('地名描述', blank=True)
    collation_status = models.CharField(
        '校勘状态',
        max_length=20,
        choices=COLLATION_STATUS_CHOICES,
        default='pending'
    )
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

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

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
        return not (has_relations or has_notes or has_disputes)

    def delete_with_check(self):
        if not self.can_delete():
            raise ValidationError('该地名存在关联关系、校勘意见或争议记录，无法删除')
        self.delete()


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
    description = models.TextField('关系说明', blank=True)
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

        if self.confirmed and self.pk is None:
            existing = NameRelation.objects.filter(
                models.Q(name_a=self.name_a, name_b=self.name_b) |
                models.Q(name_a=self.name_b, name_b=self.name_a),
                confirmed=True
            ).exists()
            if existing:
                raise ValidationError('已确认的异名关系不能重复创建')

    def save(self, *args, **kwargs):
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
        ('open', '未解决'),
        ('resolved', '已解决'),
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
    resolution = models.TextField('解决方案', blank=True)
    resolved_date = models.DateField('解决日期', null=True, blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '争议记录'
        verbose_name_plural = '争议记录'
        ordering = ['-created_at']

    def __str__(self):
        status_text = '未解决' if self.status == 'open' else '已解决'
        return f'[{status_text}] {self.place_name.name} - {self.title}'

    def save(self, *args, **kwargs):
        if self.status == 'resolved' and not self.resolved_date:
            self.resolved_date = timezone.now().date()
        super().save(*args, **kwargs)
        self._update_place_collation_status()

    def _update_place_collation_status(self):
        place = self.place_name
        if place.has_unresolved_disputes():
            if place.collation_status == 'completed':
                place.collation_status = 'in_progress'
                place.save(update_fields=['collation_status'])
