import json
from django.db.models import Q, Count
from django.shortcuts import render, get_object_or_404
from .models import (
    PlaceName,
    Literature,
    NameRelation,
    CollationNote,
    Dispute,
    PlaceNameLiterature,
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


def graph_view(request):
    return render(request, 'places/graph.html')


def graph_data(request):
    min_reliability = request.GET.get('min_reliability', '')
    region = request.GET.get('region', '')
    start_year = request.GET.get('start_year', '')

    relations = NameRelation.objects.filter(confirmed=True).select_related(
        'name_a', 'name_b'
    )

    if min_reliability:
        try:
            rel_min = int(min_reliability)
            relations = relations.filter(reliability__gte=rel_min)
        except ValueError:
            pass

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
                'description': rel.description,
            }
        })

    places = PlaceName.objects.filter(id__in=place_ids)

    if region:
        places = places.filter(region__icontains=region)
        valid_ids = set(places.values_list('id', flat=True))
        edges = [
            e for e in edges
            if int(e['data']['source'].split('_')[1]) in valid_ids
            and int(e['data']['target'].split('_')[1]) in valid_ids
        ]

    if start_year:
        places = places.filter(start_year__icontains=start_year)
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

    from django.http import JsonResponse
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
