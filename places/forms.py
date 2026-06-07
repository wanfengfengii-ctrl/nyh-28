from django import forms
from .models import (
    Literature,
    PlaceName,
    NameRelation,
    CollationNote,
    Dispute,
    PlaceNameLiterature,
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
            'reliability', 'description', 'collation_status', 'longitude', 'latitude'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'alternative_name': forms.TextInput(attrs={'class': 'form-input'}),
            'region': forms.TextInput(attrs={'class': 'form-input'}),
            'start_year': forms.TextInput(attrs={'class': 'form-input'}),
            'end_year': forms.TextInput(attrs={'class': 'form-input'}),
            'reliability': forms.NumberInput(attrs={'class': 'form-input', 'min': 0, 'max': 100}),
            'description': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 4}),
            'collation_status': forms.Select(attrs={'class': 'form-select'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.0001'}),
            'latitude': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.0001'}),
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
        fields = ['name_a', 'name_b', 'relation_type', 'reliability', 'confirmed', 'description']
        widgets = {
            'name_a': forms.Select(attrs={'class': 'form-select'}),
            'name_b': forms.Select(attrs={'class': 'form-select'}),
            'relation_type': forms.Select(attrs={'class': 'form-select'}),
            'reliability': forms.NumberInput(attrs={'class': 'form-input', 'min': 0, 'max': 100}),
            'confirmed': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'description': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 4}),
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
        fields = ['title', 'content', 'proposer', 'status', 'resolution', 'resolved_date']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input'}),
            'content': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 5}),
            'proposer': forms.TextInput(attrs={'class': 'form-input'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'resolution': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}),
            'resolved_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
        }
