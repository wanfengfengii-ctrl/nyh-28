import json
from django.db.models import Q, Count
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.urls import reverse
from django.http import JsonResponse
from .models import (
    PlaceName,
    Literature,
    NameRelation,
    CollationNote,
    Dispute,
    PlaceNameLiterature,
)
from .forms import (
    LiteratureForm,
    PlaceNameForm,
    NameRelationForm,
    CollationNoteForm,
    DisputeForm,
    PlaceNameLiteratureForm,
)


def index(request):
    total_places = PlaceName.objects.count()
    total_relations = NameRelation.objects.filter(confirmed=True).count()
    total_literatures = Literature.objects.count()
    open_disputes = Dispute.objects.filter(status='open').count()
    recent_places = PlaceName.objects.order_by('-created_at')[:5]
    recent_relations = NameRelation.objects.filter(
        confirmed=True
    ).select_related('name_a', 'name_b').order_by('-created_at')[:5]

    context = {
        'total_places': total_places,
        'total_relations': total_relations,
        'total_literatures': total_literatures,
        'open_disputes': open_disputes,
        'recent_places': recent_places,
        'recent_relations': recent_relations,
    }
    return render(request, 'places/index.html', context)


def place_list(request):
    places = PlaceName.objects.all().prefetch_related('literatures')

    search_query = request.GET.get('q', '')
    region = request.GET.get('region', '')
    min_reliability = request.GET.get('min_reliability', '')
    max_reliability = request.GET.get('max_reliability', '')
    start_year = request.GET.get('start_year', '')
    end_year = request.GET.get('end_year', '')
    collation_status = request.GET.get('collation_status', '')

    if search_query:
        places = places.filter(
            Q(name__icontains=search_query) |
            Q(alternative_name__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    if region:
        places = places.filter(region__icontains=region)

    if min_reliability:
        try:
            places = places.filter(reliability__gte=int(min_reliability))
        except ValueError:
            pass

    if max_reliability:
        try:
            places = places.filter(reliability__lte=int(max_reliability))
        except ValueError:
            pass

    if start_year:
        places = places.filter(start_year__icontains=start_year)

    if end_year:
        places = places.filter(end_year__icontains=end_year)

    if collation_status:
        places = places.filter(collation_status=collation_status)

    regions = PlaceName.objects.values_list(
        'region', flat=True
    ).distinct().order_by('region')
    regions = [r for r in regions if r]

    context = {
        'places': places,
        'search_query': search_query,
        'region': region,
        'min_reliability': min_reliability,
        'max_reliability': max_reliability,
        'start_year': start_year,
        'end_year': end_year,
        'collation_status': collation_status,
        'regions': regions,
        'collation_status_choices': PlaceName.COLLATION_STATUS_CHOICES,
    }
    return render(request, 'places/place_list.html', context)


def place_detail(request, pk):
    place = get_object_or_404(PlaceName.objects.prefetch_related('literatures'), pk=pk)

    relations = NameRelation.objects.filter(
        Q(name_a=place) | Q(name_b=place)
    ).select_related('name_a', 'name_b').order_by('-confirmed', '-created_at')

    collation_notes = place.collation_notes.all().order_by('-collation_date')
    disputes = place.disputes.all().order_by('-created_at')
    literature_relations = PlaceNameLiterature.objects.filter(
        place_name=place
    ).select_related('literature')

    related_places = []
    for rel in relations:
        other = rel.get_other_name(place)
        related_places.append({
            'place': other,
            'relation': rel,
        })

    context = {
        'place': place,
        'relations': relations,
        'related_places': related_places,
        'collation_notes': collation_notes,
        'disputes': disputes,
        'literature_relations': literature_relations,
        'can_delete': place.can_delete(),
    }
    return render(request, 'places/place_detail.html', context)


def place_create(request):
    if request.method == 'POST':
        form = PlaceNameForm(request.POST)
        if form.is_valid():
            place = form.save()
            literature_id = request.POST.get('literature')
            citation_detail = request.POST.get('citation_detail', '')
            if literature_id:
                try:
                    literature = Literature.objects.get(id=literature_id)
                    PlaceNameLiterature.objects.create(
                        place_name=place,
                        literature=literature,
                        citation_detail=citation_detail
                    )
                    messages.success(request, f'古地名 "{place.name}" 创建成功！')
                    return redirect('places:place_detail', pk=place.pk)
                except Literature.DoesNotExist:
                    form.add_error(None, '请选择有效的文献出处')
            else:
                form.add_error(None, '地名记录不能缺少文献出处，请至少选择一条文献')
    else:
        form = PlaceNameForm()

    literatures = Literature.objects.all().order_by('title')
    context = {
        'form': form,
        'literatures': literatures,
        'form_title': '新增古地名',
    }
    return render(request, 'places/form.html', context)


def place_delete(request, pk):
    place = get_object_or_404(PlaceName, pk=pk)
    if request.method == 'POST':
        if place.can_delete():
            place_name = place.name
            place.delete()
            messages.success(request, f'古地名 "{place_name}" 已成功删除')
            return redirect('places:place_list')
        else:
            messages.error(request, '该地名存在关联关系、校勘意见或争议记录，无法删除')

    context = {
        'object': place,
        'object_name': place.name,
        'object_type': '古地名',
        'can_delete': place.can_delete(),
        'cancel_url': reverse('places:place_detail', args=[pk]),
    }
    return render(request, 'places/delete_confirm.html', context)


def relation_list(request):
    relations = NameRelation.objects.select_related(
        'name_a', 'name_b'
    ).all().order_by('-confirmed', '-created_at')

    relation_type = request.GET.get('type', '')
    confirmed = request.GET.get('confirmed', '')
    min_reliability = request.GET.get('min_reliability', '')

    if relation_type:
        relations = relations.filter(relation_type=relation_type)

    if confirmed:
        if confirmed == 'yes':
            relations = relations.filter(confirmed=True)
        elif confirmed == 'no':
            relations = relations.filter(confirmed=False)

    if min_reliability:
        try:
            relations = relations.filter(reliability__gte=int(min_reliability))
        except ValueError:
            pass

    context = {
        'relations': relations,
        'relation_type': relation_type,
        'confirmed': confirmed,
        'min_reliability': min_reliability,
        'relation_type_choices': NameRelation.RELATION_TYPE_CHOICES,
    }
    return render(request, 'places/relation_list.html', context)


def relation_create(request):
    name_a_id = request.GET.get('name_a', '')
    if request.method == 'POST':
        form = NameRelationForm(request.POST)
        if form.is_valid():
            try:
                relation = form.save()
                messages.success(request, '异名关系创建成功！')
                name_a_id_post = request.POST.get('name_a')
                if name_a_id_post:
                    return redirect('places:place_detail', pk=name_a_id_post)
                return redirect('places:relation_list')
            except Exception as e:
                form.add_error(None, str(e))
    else:
        if name_a_id:
            form = NameRelationForm(initial={'name_a': name_a_id})
        else:
            form = NameRelationForm()

    context = {
        'form': form,
        'form_title': '新增异名关系',
    }
    return render(request, 'places/form.html', context)


def relation_delete(request, pk):
    relation = get_object_or_404(NameRelation, pk=pk)
    if request.method == 'POST':
        relation_desc = str(relation)
        relation.delete()
        messages.success(request, f'异名关系 "{relation_desc}" 已成功删除')
        return redirect('places:relation_list')

    context = {
        'object': relation,
        'object_name': str(relation),
        'object_type': '异名关系',
        'can_delete': True,
        'cancel_url': reverse('places:relation_list'),
    }
    return render(request, 'places/delete_confirm.html', context)


def graph_view(request):
    return render(request, 'places/graph.html')


def graph_data(request):
    min_reliability = request.GET.get('min_reliability', '')
    max_reliability = request.GET.get('max_reliability', '')
    region = request.GET.get('region', '')
    start_year = request.GET.get('start_year', '')
    end_year = request.GET.get('end_year', '')
    year_keyword = request.GET.get('year', '')
    relation_type = request.GET.get('type', '')
    collation_status = request.GET.get('collation_status', '')

    relations = NameRelation.objects.filter(confirmed=True).select_related(
        'name_a', 'name_b'
    )

    if min_reliability:
        try:
            rel_min = int(min_reliability)
            relations = relations.filter(reliability__gte=rel_min)
        except ValueError:
            pass

    if max_reliability:
        try:
            rel_max = int(max_reliability)
            relations = relations.filter(reliability__lte=rel_max)
        except ValueError:
            pass

    if relation_type:
        relations = relations.filter(relation_type=relation_type)

    place_ids = set()
    edges = []

    for rel in relations:
        place_ids.add(rel.name_a.id)
        place_ids.add(rel.name_b.id)
        edges.append({
            'data': {
                'id': f'edge_{rel.id}',
                'source': f'node_{rel.name_a.id}',
                'target': f'node_{rel.name_b.id}',
                'relation_type': rel.get_relation_type_display(),
                'reliability': rel.reliability,
                'relation_type_value': rel.relation_type,
                'description': rel.description,
            }
        })

    places = PlaceName.objects.filter(id__in=place_ids)

    if region:
        places = places.filter(region__icontains=region)

    if start_year:
        places = places.filter(start_year__icontains=start_year)

    if end_year:
        places = places.filter(end_year__icontains=end_year)

    if year_keyword:
        places = places.filter(
            Q(start_year__icontains=year_keyword) |
            Q(end_year__icontains=year_keyword)
        )

    if collation_status:
        places = places.filter(collation_status=collation_status)

    valid_ids = set(places.values_list('id', flat=True))
    edges = [
        e for e in edges
        if int(e['data']['source'].split('_')[1]) in valid_ids
        and int(e['data']['target'].split('_')[1]) in valid_ids
    ]

    nodes = []
    for place in places:
        nodes.append({
            'data': {
                'id': f'node_{place.id}',
                'label': place.name,
                'alternative_name': place.alternative_name,
                'region': place.region,
                'start_year': place.start_year,
                'end_year': place.end_year,
                'reliability': place.reliability,
                'collation_status': place.get_collation_status_display(),
                'collation_status_value': place.collation_status,
                'url': f'/places/{place.id}/',
            }
        })

    elements = nodes + edges

    regions = PlaceName.objects.values_list(
        'region', flat=True
    ).distinct().order_by('region')
    regions = [r for r in regions if r]

    data = {
        'elements': elements,
        'regions': regions,
    }

    return JsonResponse(data)


def literature_list(request):
    literatures = Literature.objects.all().order_by('title')
    search_query = request.GET.get('q', '')
    dynasty = request.GET.get('dynasty', '')

    if search_query:
        literatures = literatures.filter(
            Q(title__icontains=search_query) |
            Q(author__icontains=search_query)
        )

    if dynasty:
        literatures = literatures.filter(dynasty__icontains=dynasty)

    dynasties = Literature.objects.values_list(
        'dynasty', flat=True
    ).distinct().order_by('dynasty')
    dynasties = [d for d in dynasties if d]

    context = {
        'literatures': literatures,
        'search_query': search_query,
        'dynasty': dynasty,
        'dynasties': dynasties,
    }
    return render(request, 'places/literature_list.html', context)


def literature_create(request):
    if request.method == 'POST':
        form = LiteratureForm(request.POST)
        if form.is_valid():
            literature = form.save()
            messages.success(request, f'文献 "{literature.title}" 创建成功！')
            return redirect('places:literature_list')
    else:
        form = LiteratureForm()

    context = {
        'form': form,
        'form_title': '新增文献出处',
    }
    return render(request, 'places/form.html', context)


def literature_delete(request, pk):
    literature = get_object_or_404(Literature, pk=pk)
    can_delete = not literature.placename_set.exists()

    if request.method == 'POST':
        if can_delete:
            lit_title = literature.title
            literature.delete()
            messages.success(request, f'文献 "{lit_title}" 已成功删除')
            return redirect('places:literature_list')
        else:
            messages.error(request, '该文献已被地名引用，无法删除')

    context = {
        'object': literature,
        'object_name': literature.title,
        'object_type': '文献出处',
        'can_delete': can_delete,
        'cancel_url': reverse('places:literature_list'),
    }
    return render(request, 'places/delete_confirm.html', context)


def dispute_list(request):
    disputes = Dispute.objects.select_related(
        'place_name'
    ).all().order_by('-created_at')

    status = request.GET.get('status', '')

    if status:
        disputes = disputes.filter(status=status)

    context = {
        'disputes': disputes,
        'status': status,
        'status_choices': Dispute.STATUS_CHOICES,
    }
    return render(request, 'places/dispute_list.html', context)


def dispute_create(request):
    place_id = request.GET.get('place_id', '')
    if request.method == 'POST':
        form = DisputeForm(request.POST)
        if form.is_valid():
            dispute = form.save(commit=False)
            place_id = request.POST.get('place_id')
            if place_id:
                try:
                    place = PlaceName.objects.get(id=place_id)
                    dispute.place_name = place
                    dispute.save()
                    messages.success(request, f'争议记录 "{dispute.title}" 创建成功！')
                    return redirect('places:place_detail', pk=place.pk)
                except PlaceName.DoesNotExist:
                    form.add_error(None, '请选择有效的地名')
            else:
                form.add_error(None, '请选择关联的地名')
    else:
        form = DisputeForm()

    places = PlaceName.objects.all().order_by('name')
    context = {
        'form': form,
        'places': places,
        'selected_place_id': place_id,
        'form_title': '新增争议记录',
    }
    return render(request, 'places/form_with_place.html', context)


def dispute_delete(request, pk):
    dispute = get_object_or_404(Dispute.objects.select_related('place_name'), pk=pk)
    place_pk = dispute.place_name.pk if dispute.place_name else None

    if request.method == 'POST':
        dispute_title = dispute.title
        dispute.delete()
        messages.success(request, f'争议记录 "{dispute_title}" 已成功删除')
        if place_pk:
            return redirect('places:place_detail', pk=place_pk)
        return redirect('places:dispute_list')

    context = {
        'object': dispute,
        'object_name': dispute.title,
        'object_type': '争议记录',
        'can_delete': True,
        'cancel_url': reverse('places:place_detail', args=[place_pk]) if place_pk else reverse('places:dispute_list'),
    }
    return render(request, 'places/delete_confirm.html', context)


def collation_list(request):
    notes = CollationNote.objects.select_related(
        'place_name'
    ).all().order_by('-collation_date')

    place_name = request.GET.get('place_name', '')
    collator = request.GET.get('collator', '')

    if place_name:
        notes = notes.filter(place_name__name__icontains=place_name)

    if collator:
        notes = notes.filter(collator__icontains=collator)

    context = {
        'notes': notes,
        'place_name': place_name,
        'collator': collator,
    }
    return render(request, 'places/collation_list.html', context)


def collation_create(request):
    place_id = request.GET.get('place_id', '')
    if request.method == 'POST':
        form = CollationNoteForm(request.POST)
        if form.is_valid():
            note = form.save(commit=False)
            place_id = request.POST.get('place_id')
            if place_id:
                try:
                    place = PlaceName.objects.get(id=place_id)
                    note.place_name = place
                    note.save()
                    messages.success(request, f'校勘意见 "{note.title}" 创建成功！')
                    return redirect('places:place_detail', pk=place.pk)
                except PlaceName.DoesNotExist:
                    form.add_error(None, '请选择有效的地名')
            else:
                form.add_error(None, '请选择关联的地名')
    else:
        form = CollationNoteForm()

    places = PlaceName.objects.all().order_by('name')
    context = {
        'form': form,
        'places': places,
        'selected_place_id': place_id,
        'form_title': '新增校勘意见',
    }
    return render(request, 'places/form_with_place.html', context)


def collation_delete(request, pk):
    note = get_object_or_404(CollationNote.objects.select_related('place_name'), pk=pk)
    place_pk = note.place_name.pk if note.place_name else None

    if request.method == 'POST':
        note_title = note.title
        note.delete()
        messages.success(request, f'校勘意见 "{note_title}" 已成功删除')
        if place_pk:
            return redirect('places:place_detail', pk=place_pk)
        return redirect('places:collation_list')

    context = {
        'object': note,
        'object_name': note.title,
        'object_type': '校勘意见',
        'can_delete': True,
        'cancel_url': reverse('places:place_detail', args=[place_pk]) if place_pk else reverse('places:collation_list'),
    }
    return render(request, 'places/delete_confirm.html', context)
