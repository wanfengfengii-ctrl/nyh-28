from django import forms
from .models import (
    Literature,
    PlaceName,
    NameRelation,
    CollationNote,
    Dispute,
    PlaceNameLiterature,
    DeletionRequest,
    Annotation,
    ReviewRecord,
)


class LiteratureForm(forms.ModelForm):
    class Meta:
        model = Literature
        fields = ['title', 'author', 'dynasty', 'publisher', 'volume', 'page', 'note']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input'}),
            'author': forms.TextInput(attrs={'class': 'form-input'}),
            'dynasty': forms.TextInput(attrs={'class': 'form-input'}),
            'publisher': forms.TextInput(attrs={'class': 'form-input'}),
            'volume': forms.TextInput(attrs={'class': 'form-input'}),
            'page': forms.TextInput(attrs={'class': 'form-input'}),
            'note': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}),
        }


class PlaceNameForm(forms.ModelForm):
    class Meta:
        model = PlaceName
        fields = [
            'name', 'alternative_name', 'region', 'start_year', 'end_year',
            'start_year_num', 'end_year_num', 'reliability', 'description',
            'collation_status', 'longitude', 'latitude'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'alternative_name': forms.TextInput(attrs={'class': 'form-input'}),
            'region': forms.TextInput(attrs={'class': 'form-input'}),
            'start_year': forms.TextInput(attrs={'class': 'form-input'}),
            'end_year': forms.TextInput(attrs={'class': 'form-input'}),
            'start_year_num': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '如：618'}),
            'end_year_num': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '如：907'}),
            'reliability': forms.NumberInput(attrs={'class': 'form-input', 'min': 0, 'max': 100}),
            'description': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 4}),
            'collation_status': forms.Select(attrs={'class': 'form-select'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.0001'}),
            'latitude': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.0001'}),
        }


class PlaceNameSubmitForm(forms.ModelForm):
    class Meta:
        model = PlaceName
        fields = [
            'name', 'alternative_name', 'region', 'start_year', 'end_year',
            'start_year_num', 'end_year_num', 'reliability', 'description',
            'longitude', 'latitude', 'submitter'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'alternative_name': forms.TextInput(attrs={'class': 'form-input'}),
            'region': forms.TextInput(attrs={'class': 'form-input'}),
            'start_year': forms.TextInput(attrs={'class': 'form-input'}),
            'end_year': forms.TextInput(attrs={'class': 'form-input'}),
            'start_year_num': forms.NumberInput(attrs={'class': 'form-input'}),
            'end_year_num': forms.NumberInput(attrs={'class': 'form-input'}),
            'reliability': forms.NumberInput(attrs={'class': 'form-input', 'min': 0, 'max': 100}),
            'description': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 4}),
            'longitude': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.0001'}),
            'latitude': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.0001'}),
            'submitter': forms.TextInput(attrs={'class': 'form-input'}),
        }


class PlaceNameLiteratureForm(forms.ModelForm):
    class Meta:
        model = PlaceNameLiterature
        fields = ['literature', 'citation_detail']
        widgets = {
            'literature': forms.Select(attrs={'class': 'form-select'}),
            'citation_detail': forms.TextInput(attrs={'class': 'form-input'}),
        }


class NameRelationForm(forms.ModelForm):
    class Meta:
        model = NameRelation
        fields = ['name_a', 'name_b', 'relation_type', 'reliability', 'status', 'description', 'proposer']
        widgets = {
            'name_a': forms.Select(attrs={'class': 'form-select'}),
            'name_b': forms.Select(attrs={'class': 'form-select'}),
            'relation_type': forms.Select(attrs={'class': 'form-select'}),
            'reliability': forms.NumberInput(attrs={'class': 'form-input', 'min': 0, 'max': 100}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 4}),
            'proposer': forms.TextInput(attrs={'class': 'form-input'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        name_a = cleaned_data.get('name_a')
        name_b = cleaned_data.get('name_b')
        if name_a and name_b and name_a == name_b:
            raise forms.ValidationError('同一名称不能关联到自身')
        return cleaned_data


class CollationNoteForm(forms.ModelForm):
    class Meta:
        model = CollationNote
        fields = ['title', 'content', 'conclusion', 'collator', 'collation_date']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input'}),
            'content': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 5}),
            'conclusion': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}),
            'collator': forms.TextInput(attrs={'class': 'form-input'}),
            'collation_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
        }


class DisputeForm(forms.ModelForm):
    class Meta:
        model = Dispute
        fields = ['title', 'content', 'proposer', 'status', 'resolution_type', 'resolution', 'resolved_date']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input'}),
            'content': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 5}),
            'proposer': forms.TextInput(attrs={'class': 'form-input'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'resolution_type': forms.Select(attrs={'class': 'form-select'}),
            'resolution': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}),
            'resolved_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
        }


class DisputeResolveForm(forms.Form):
    resolution_type = forms.ChoiceField(
        choices=Dispute.RESOLUTION_TYPE_CHOICES[1:],
        label='解决方式',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    resolution = forms.CharField(
        label='解决方案',
        widget=forms.Textarea(attrs={'class': 'form-textarea', 'rows': 4}),
        required=True
    )
    resolver = forms.CharField(
        label='处理人',
        widget=forms.TextInput(attrs={'class': 'form-input'}),
        required=False
    )


class DisputeReopenForm(forms.Form):
    reason = forms.CharField(
        label='重新开启理由',
        widget=forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}),
        required=True
    )
    reopener = forms.CharField(
        label='申请人',
        widget=forms.TextInput(attrs={'class': 'form-input'}),
        required=False
    )


class DeletionRequestForm(forms.ModelForm):
    class Meta:
        model = DeletionRequest
        fields = ['reason', 'applicant']
        widgets = {
            'reason': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 4}),
            'applicant': forms.TextInput(attrs={'class': 'form-input'}),
        }


class DeletionReviewForm(forms.Form):
    ACTION_CHOICES = [
        ('approve', '批准删除'),
        ('reject', '驳回申请'),
    ]
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        label='审核操作',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    comment = forms.CharField(
        label='审核意见',
        widget=forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}),
        required=False
    )
    reviewer = forms.CharField(
        label='审核人',
        widget=forms.TextInput(attrs={'class': 'form-input'}),
        required=False
    )

    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        comment = cleaned_data.get('comment')
        if action == 'reject' and not comment:
            raise forms.ValidationError('驳回删除申请时必须填写审核意见')
        return cleaned_data


class ReviewForm(forms.Form):
    ACTION_CHOICES = [
        ('approve', '审核通过'),
        ('reject', '审核驳回'),
    ]
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        label='审核操作',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    comment = forms.CharField(
        label='审核意见',
        widget=forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}),
        required=False
    )
    reviewer = forms.CharField(
        label='审核人',
        widget=forms.TextInput(attrs={'class': 'form-input'}),
        required=False
    )

    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        comment = cleaned_data.get('comment')
        if action == 'reject' and not comment:
            raise forms.ValidationError('驳回时必须填写审核意见')
        return cleaned_data


class AnnotationForm(forms.ModelForm):
    class Meta:
        model = Annotation
        fields = ['content', 'author', 'reply_to']
        widgets = {
            'content': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}),
            'author': forms.TextInput(attrs={'class': 'form-input'}),
            'reply_to': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['reply_to'].required = False


class LiteratureCitationForm(forms.ModelForm):
    class Meta:
        model = PlaceNameLiterature
        fields = ['literature', 'citation_detail']
        widgets = {
            'literature': forms.Select(attrs={'class': 'form-select'}),
            'citation_detail': forms.TextInput(attrs={'class': 'form-input'}),
        }
