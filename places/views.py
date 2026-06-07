import json
from django.db.models import Q, Count
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.urls import reverse
from django.http import JsonResponse
from django.utils import timezone
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from .models import (
    PlaceName,
    Literature,
    NameRelation,
    CollationNote,
    Dispute,
    PlaceNameLiterature,
    DeletionRequest,
    ReviewRecord,
    Annotation,
    OperationLog,
    PlaceNameVersion,
    MigrationRecord,
    MigrationStage,
    MigrationEvidence,
    MigrationDispute,
    MigrationVersion,
)
from .forms import (
    LiteratureForm,
    PlaceNameForm,
    PlaceNameSubmitForm,
    NameRelationForm,
    CollationNoteForm,
    DisputeForm,
    DisputeResolveForm,
    DisputeReopenForm,
    PlaceNameLiteratureForm,
    DeletionRequestForm,
    DeletionReviewForm,
    ReviewForm,
    AnnotationForm,
    LiteratureCitationForm,
    MigrationRecordForm,
    MigrationRecordEditForm,
    MigrationStageForm,
    MigrationEvidenceForm,
    MigrationDisputeForm,
    MigrationReviewForm,
)


def _get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def index(request):
    total_places = PlaceName.objects.count()
    total_relations = NameRelation.objects.filter(status='confirmed').count()
    total_literatures = Literature.objects.count()
    open_disputes = Dispute.objects.filter(status__in=['open', 'investigating']).count()
    pending_reviews = PlaceName.objects.filter(review_status='submitted').count()
    pending_deletions = DeletionRequest.objects.filter(status__in=['pending', 'reviewing']).count()
    recent_places = PlaceName.objects.order_by('-created_at')[:5]
    recent_relations = NameRelation.objects.filter(
        status='confirmed'
    ).select_related('name_a', 'name_b').order_by('-created_at')[:5]
    recent_logs = OperationLog.objects.all()[:10]

    context = {
        'total_places': total_places,
        'total_relations': total_relations,
        'total_literatures': total_literatures,
        'open_disputes': open_disputes,
        'pending_reviews': pending_reviews,
        'pending_deletions': pending_deletions,
        'recent_places': recent_places,
        'recent_relations': recent_relations,
        'recent_logs': recent_logs,
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
    review_status = request.GET.get('review_status', '')

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

    if review_status:
        places = places.filter(review_status=review_status)

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
        'review_status': review_status,
        'regions': regions,
        'collation_status_choices': PlaceName.COLLATION_STATUS_CHOICES,
        'review_status_choices': PlaceName.REVIEW_STATUS_CHOICES,
    }
    return render(request, 'places/place_list.html', context)


def place_detail(request, pk):
    place = get_object_or_404(PlaceName.objects.prefetch_related('literatures'), pk=pk)

    relations = NameRelation.objects.filter(
        Q(name_a=place) | Q(name_b=place)
    ).select_related('name_a', 'name_b').order_by('-status', '-created_at')

    collation_notes = place.collation_notes.all().order_by('-collation_date')
    disputes = place.disputes.all().order_by('-created_at')
    literature_relations = PlaceNameLiterature.objects.filter(
        place_name=place
    ).select_related('literature')
    versions = place.versions.all()[:10]
    annotations = Annotation.objects.filter(
        target_type='place', target_id=place.id
    ).order_by('-created_at')
    review_records = place.review_records.all().order_by('-created_at')
    deletion_requests = place.deletion_requests.all().order_by('-created_at')
    migration_records = MigrationRecord.objects.filter(
        place_name=place
    ).order_by('-created_at')

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
        'versions': versions,
        'annotations': annotations,
        'review_records': review_records,
        'deletion_requests': deletion_requests,
        'migration_records': migration_records,
        'can_delete': place.can_delete(),
        'annotation_form': AnnotationForm(),
    }
    return render(request, 'places/place_detail.html', context)


def place_create(request):
    if request.method == 'POST':
        form = PlaceNameSubmitForm(request.POST)
        if form.is_valid():
            place = form.save(commit=False)
            place.review_status = 'draft'
            place.save()

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
                    OperationLog.log(
                        target_type='place',
                        target_id=place.id,
                        action='create',
                        target_name=place.name,
                        operator=form.cleaned_data.get('submitter', ''),
                        detail='创建地名记录（草稿）',
                        ip_address=_get_client_ip(request),
                    )
                    messages.success(request, f'古地名 "{place.name}" 创建成功！')
                    return redirect('places:place_detail', pk=place.pk)
                except Literature.DoesNotExist:
                    form.add_error(None, '请选择有效的文献出处')
            else:
                form.add_error(None, '地名记录不能缺少文献出处，请至少选择一条文献')
    else:
        form = PlaceNameSubmitForm()

    literatures = Literature.objects.all().order_by('title')
    context = {
        'form': form,
        'literatures': literatures,
        'form_title': '新增古地名',
    }
    return render(request, 'places/form_with_place.html', context)


def place_edit(request, pk):
    place = get_object_or_404(PlaceName, pk=pk)

    if place.review_status == 'archived':
        messages.error(request, '已归档的地名不能编辑')
        return redirect('places:place_detail', pk=pk)

    if request.method == 'POST':
        form = PlaceNameForm(request.POST, instance=place)
        if form.is_valid():
            place = form.save()
            OperationLog.log(
                target_type='place',
                target_id=place.id,
                action='update',
                target_name=place.name,
                detail='更新地名信息',
                ip_address=_get_client_ip(request),
            )
            messages.success(request, f'古地名 "{place.name}" 更新成功！')
            return redirect('places:place_detail', pk=place.pk)
    else:
        form = PlaceNameForm(instance=place)

    context = {
        'form': form,
        'form_title': '编辑古地名',
    }
    return render(request, 'places/form.html', context)


def place_submit(request, pk):
    place = get_object_or_404(PlaceName, pk=pk)

    if request.method == 'POST':
        submitter = request.POST.get('submitter', '')
        try:
            place.submit_for_review(submitter=submitter)
            ReviewRecord.objects.create(
                place_name=place,
                action='submit',
                operator=submitter,
            )
            OperationLog.log(
                target_type='place',
                target_id=place.id,
                action='submit',
                target_name=place.name,
                operator=submitter,
                detail='提交审核',
                ip_address=_get_client_ip(request),
            )
            messages.success(request, f'古地名 "{place.name}" 已提交审核！')
            return redirect('places:place_detail', pk=pk)
        except ValidationError as e:
            messages.error(request, str(e))

    context = {
        'place': place,
    }
    return render(request, 'places/place_submit.html', context)


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


def place_archive(request, pk):
    place = get_object_or_404(PlaceName, pk=pk)

    if request.method == 'POST':
        try:
            place.archive()
            ReviewRecord.objects.create(
                place_name=place,
                action='archive',
            )
            OperationLog.log(
                target_type='place',
                target_id=place.id,
                action='archive',
                target_name=place.name,
                detail='归档地名',
                ip_address=_get_client_ip(request),
            )
            messages.success(request, f'古地名 "{place.name}" 已归档！')
            return redirect('places:place_detail', pk=pk)
        except ValidationError as e:
            messages.error(request, str(e))

    context = {
        'place': place,
    }
    return render(request, 'places/place_archive.html', context)


def review_list(request):
    places = PlaceName.objects.filter(
        review_status__in=['submitted', 'reviewing']
    ).order_by('-submitted_at')

    status = request.GET.get('status', '')
    if status:
        places = places.filter(review_status=status)

    context = {
        'places': places,
        'status': status,
    }
    return render(request, 'places/review_list.html', context)


def review_detail(request, pk):
    place = get_object_or_404(PlaceName, pk=pk)
    review_records = place.review_records.all().order_by('-created_at')

    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data['action']
            comment = form.cleaned_data['comment']
            reviewer = form.cleaned_data['reviewer']

            try:
                if action == 'approve':
                    place.approve(reviewer=reviewer, comment=comment)
                    ReviewRecord.objects.create(
                        place_name=place,
                        action='approve',
                        operator=reviewer,
                        comment=comment,
                    )
                    OperationLog.log(
                        target_type='place',
                        target_id=place.id,
                        action='approve',
                        target_name=place.name,
                        operator=reviewer,
                        detail=f'审核通过：{comment}',
                        ip_address=_get_client_ip(request),
                    )
                    messages.success(request, f'古地名 "{place.name}" 审核通过！')
                else:
                    place.reject(reviewer=reviewer, comment=comment)
                    ReviewRecord.objects.create(
                        place_name=place,
                        action='reject',
                        operator=reviewer,
                        comment=comment,
                    )
                    OperationLog.log(
                        target_type='place',
                        target_id=place.id,
                        action='reject',
                        target_name=place.name,
                        operator=reviewer,
                        detail=f'审核驳回：{comment}',
                        ip_address=_get_client_ip(request),
                    )
                    messages.success(request, f'古地名 "{place.name}" 已驳回。')
                return redirect('places:review_list')
            except ValidationError as e:
                form.add_error(None, str(e))
    else:
        form = ReviewForm()

    context = {
        'place': place,
        'form': form,
        'review_records': review_records,
    }
    return render(request, 'places/review_detail.html', context)


def version_history(request, pk):
    place = get_object_or_404(PlaceName, pk=pk)
    versions = place.versions.all().order_by('-version_number')

    context = {
        'place': place,
        'versions': versions,
    }
    return render(request, 'places/version_history.html', context)


def relation_list(request):
    relations = NameRelation.objects.select_related(
        'name_a', 'name_b'
    ).all().order_by('-status', '-created_at')

    relation_type = request.GET.get('type', '')
    status = request.GET.get('status', '')
    min_reliability = request.GET.get('min_reliability', '')
    max_reliability = request.GET.get('max_reliability', '')

    if relation_type:
        relations = relations.filter(relation_type=relation_type)

    if status:
        relations = relations.filter(status=status)

    if min_reliability:
        try:
            relations = relations.filter(reliability__gte=int(min_reliability))
        except ValueError:
            pass

    if max_reliability:
        try:
            relations = relations.filter(reliability__lte=int(max_reliability))
        except ValueError:
            pass

    context = {
        'relations': relations,
        'relation_type': relation_type,
        'status': status,
        'min_reliability': min_reliability,
        'max_reliability': max_reliability,
        'relation_type_choices': NameRelation.RELATION_TYPE_CHOICES,
        'status_choices': NameRelation.STATUS_CHOICES,
    }
    return render(request, 'places/relation_list.html', context)


def relation_create(request):
    name_a_id = request.GET.get('name_a', '')
    if request.method == 'POST':
        form = NameRelationForm(request.POST)
        if form.is_valid():
            try:
                relation = form.save()
                OperationLog.log(
                    target_type='relation',
                    target_id=relation.id,
                    action='create',
                    target_name=str(relation),
                    operator=form.cleaned_data.get('proposer', ''),
                    detail='创建异名关系',
                    ip_address=_get_client_ip(request),
                )
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
        OperationLog.log(
            target_type='relation',
            target_id=pk,
            action='delete',
            target_name=relation_desc,
            detail='删除异名关系',
            ip_address=_get_client_ip(request),
        )
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
    review_status = request.GET.get('review_status', '')
    relation_status = request.GET.get('relation_status', '')
    start_year_num = request.GET.get('start_year_num', '')
    end_year_num = request.GET.get('end_year_num', '')

    relations = NameRelation.objects.select_related(
        'name_a', 'name_b'
    )

    if relation_status:
        relations = relations.filter(status=relation_status)
    else:
        relations = relations.filter(status='confirmed')

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
                'relation_status': rel.get_status_display(),
                'relation_status_value': rel.status,
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

    if start_year_num:
        try:
            places = places.filter(start_year_num__gte=int(start_year_num))
        except ValueError:
            pass

    if end_year_num:
        try:
            places = places.filter(end_year_num__lte=int(end_year_num))
        except ValueError:
            pass

    if collation_status:
        places = places.filter(collation_status=collation_status)

    if review_status:
        places = places.filter(review_status=review_status)

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
                'start_year_num': place.start_year_num or 0,
                'end_year_num': place.end_year_num or 0,
                'reliability': place.reliability,
                'collation_status': place.get_collation_status_display(),
                'collation_status_value': place.collation_status,
                'review_status': place.get_review_status_display(),
                'review_status_value': place.review_status,
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


def literature_detail(request, pk):
    literature = get_object_or_404(Literature, pk=pk)
    cited_relations = PlaceNameLiterature.objects.filter(
        literature=literature
    ).select_related('place_name')

    citation_chain_data = []
    for rel in cited_relations:
        place = rel.place_name
        other_lits = PlaceNameLiterature.objects.filter(
            place_name=place
        ).exclude(literature=literature).select_related('literature')
        citation_chain_data.append({
            'place': place,
            'citation_detail': rel.citation_detail,
            'other_literatures': [r.literature for r in other_lits],
        })

    annotations = Annotation.objects.filter(
        target_type='literature', target_id=literature.id
    ).order_by('-created_at')

    context = {
        'literature': literature,
        'cited_places': cited_relations,
        'citation_chain': citation_chain_data,
        'annotations': annotations,
        'annotation_form': AnnotationForm(),
    }
    return render(request, 'places/literature_detail.html', context)


def literature_create(request):
    if request.method == 'POST':
        form = LiteratureForm(request.POST)
        if form.is_valid():
            literature = form.save()
            OperationLog.log(
                target_type='literature',
                target_id=literature.id,
                action='create',
                target_name=literature.title,
                detail='创建文献记录',
                ip_address=_get_client_ip(request),
            )
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
            OperationLog.log(
                target_type='literature',
                target_id=pk,
                action='delete',
                target_name=lit_title,
                detail='删除文献记录',
                ip_address=_get_client_ip(request),
            )
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
    resolution_type = request.GET.get('resolution_type', '')

    if status:
        disputes = disputes.filter(status=status)

    if resolution_type:
        disputes = disputes.filter(resolution_type=resolution_type)

    context = {
        'disputes': disputes,
        'status': status,
        'resolution_type': resolution_type,
        'status_choices': Dispute.STATUS_CHOICES,
        'resolution_type_choices': Dispute.RESOLUTION_TYPE_CHOICES,
    }
    return render(request, 'places/dispute_list.html', context)


def dispute_detail(request, pk):
    dispute = get_object_or_404(Dispute.objects.select_related('place_name'), pk=pk)
    annotations = Annotation.objects.filter(
        target_type='dispute', target_id=dispute.id
    ).order_by('-created_at')

    context = {
        'dispute': dispute,
        'annotations': annotations,
        'annotation_form': AnnotationForm(),
    }
    return render(request, 'places/dispute_detail.html', context)


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
                    OperationLog.log(
                        target_type='dispute',
                        target_id=dispute.id,
                        action='create',
                        target_name=dispute.title,
                        operator=form.cleaned_data.get('proposer', ''),
                        detail=f'创建争议记录（关联地名：{place.name}）',
                        ip_address=_get_client_ip(request),
                    )
                    messages.success(request, f'争议记录 "{dispute.title}" 创建成功！')
                    return redirect('places:dispute_detail', pk=dispute.pk)
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


def dispute_resolve(request, pk):
    dispute = get_object_or_404(Dispute.objects.select_related('place_name'), pk=pk)

    if request.method == 'POST':
        form = DisputeResolveForm(request.POST)
        if form.is_valid():
            try:
                dispute.resolve(
                    resolver=form.cleaned_data.get('resolver', ''),
                    resolution=form.cleaned_data['resolution'],
                    resolution_type=form.cleaned_data['resolution_type'],
                )
                OperationLog.log(
                    target_type='dispute',
                    target_id=dispute.id,
                    action='resolve',
                    target_name=dispute.title,
                    operator=form.cleaned_data.get('resolver', ''),
                    detail=f'解决争议：{form.cleaned_data["resolution"][:50]}...',
                    ip_address=_get_client_ip(request),
                )
                messages.success(request, '争议已解决！')
                return redirect('places:dispute_detail', pk=dispute.pk)
            except ValidationError as e:
                form.add_error(None, str(e))
    else:
        form = DisputeResolveForm()

    context = {
        'dispute': dispute,
        'form': form,
    }
    return render(request, 'places/dispute_resolve.html', context)


def dispute_reject(request, pk):
    dispute = get_object_or_404(Dispute.objects.select_related('place_name'), pk=pk)

    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        resolver = request.POST.get('resolver', '')
        if not reason:
            messages.error(request, '驳回争议时必须填写理由')
        else:
            try:
                dispute.reject_dispute(resolver=resolver, reason=reason)
                OperationLog.log(
                    target_type='dispute',
                    target_id=dispute.id,
                    action='reject',
                    target_name=dispute.title,
                    operator=resolver,
                    detail=f'驳回争议：{reason[:50]}...',
                    ip_address=_get_client_ip(request),
                )
                messages.success(request, '争议已驳回。')
                return redirect('places:dispute_detail', pk=dispute.pk)
            except ValidationError as e:
                messages.error(request, str(e))

    context = {
        'dispute': dispute,
    }
    return render(request, 'places/dispute_reject.html', context)


def dispute_reopen(request, pk):
    dispute = get_object_or_404(Dispute.objects.select_related('place_name'), pk=pk)

    if request.method == 'POST':
        form = DisputeReopenForm(request.POST)
        if form.is_valid():
            try:
                dispute.reopen(
                    reopener=form.cleaned_data.get('reopener', ''),
                    reason=form.cleaned_data['reason'],
                )
                OperationLog.log(
                    target_type='dispute',
                    target_id=dispute.id,
                    action='update',
                    target_name=dispute.title,
                    operator=form.cleaned_data.get('reopener', ''),
                    detail=f'重新开启争议（第{dispute.reopen_count}次）：{form.cleaned_data["reason"][:50]}...',
                    ip_address=_get_client_ip(request),
                )
                messages.success(request, '争议已重新开启！')
                return redirect('places:dispute_detail', pk=dispute.pk)
            except ValidationError as e:
                form.add_error(None, str(e))
    else:
        form = DisputeReopenForm()

    context = {
        'dispute': dispute,
        'form': form,
    }
    return render(request, 'places/dispute_reopen.html', context)


def dispute_delete(request, pk):
    dispute = get_object_or_404(Dispute.objects.select_related('place_name'), pk=pk)
    place_pk = dispute.place_name.pk if dispute.place_name else None

    if request.method == 'POST':
        dispute_title = dispute.title
        dispute.delete()
        OperationLog.log(
            target_type='dispute',
            target_id=pk,
            action='delete',
            target_name=dispute_title,
            detail='删除争议记录',
            ip_address=_get_client_ip(request),
        )
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
                    OperationLog.log(
                        target_type='collation',
                        target_id=note.id,
                        action='create',
                        target_name=note.title,
                        operator=form.cleaned_data.get('collator', ''),
                        detail=f'创建校勘意见（关联地名：{place.name}）',
                        ip_address=_get_client_ip(request),
                    )
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
        OperationLog.log(
            target_type='collation',
            target_id=pk,
            action='delete',
            target_name=note_title,
            detail='删除校勘意见',
            ip_address=_get_client_ip(request),
        )
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


def deletion_request_list(request):
    requests = DeletionRequest.objects.select_related(
        'place_name'
    ).all().order_by('-created_at')

    status = request.GET.get('status', '')
    if status:
        requests = requests.filter(status=status)

    context = {
        'deletion_requests': requests,
        'status': status,
        'status_choices': DeletionRequest.STATUS_CHOICES,
    }
    return render(request, 'places/deletion_request_list.html', context)


def deletion_request_create(request, pk):
    place = get_object_or_404(PlaceName, pk=pk)

    if request.method == 'POST':
        form = DeletionRequestForm(request.POST)
        if form.is_valid():
            try:
                deletion_req = form.save(commit=False)
                deletion_req.place_name = place
                deletion_req.save()
                OperationLog.log(
                    target_type='deletion_request',
                    target_id=deletion_req.id,
                    action='create',
                    target_name=place.name,
                    operator=form.cleaned_data.get('applicant', ''),
                    detail=f'提交删除申请：{form.cleaned_data["reason"][:50]}...',
                    ip_address=_get_client_ip(request),
                )
                messages.success(request, '删除申请已提交！')
                return redirect('places:deletion_request_detail', pk=deletion_req.pk)
            except ValidationError as e:
                form.add_error(None, str(e))
    else:
        form = DeletionRequestForm()

    context = {
        'form': form,
        'place': place,
        'form_title': '申请删除地名',
    }
    return render(request, 'places/deletion_request_create.html', context)


def deletion_request_detail(request, pk):
    deletion_req = get_object_or_404(
        DeletionRequest.objects.select_related('place_name'),
        pk=pk
    )
    annotations = Annotation.objects.filter(
        target_type='deletion_request', target_id=deletion_req.id
    ).order_by('-created_at')

    context = {
        'deletion_request': deletion_req,
        'annotations': annotations,
        'annotation_form': AnnotationForm(),
    }
    return render(request, 'places/deletion_request_detail.html', context)


def deletion_request_review(request, pk):
    deletion_req = get_object_or_404(
        DeletionRequest.objects.select_related('place_name'),
        pk=pk
    )

    if request.method == 'POST':
        form = DeletionReviewForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data['action']
            comment = form.cleaned_data['comment']
            reviewer = form.cleaned_data['reviewer']

            try:
                if action == 'approve':
                    deletion_req.approve(reviewer=reviewer, comment=comment)
                    OperationLog.log(
                        target_type='deletion_request',
                        target_id=deletion_req.id,
                        action='approve',
                        target_name=deletion_req.place_name.name,
                        operator=reviewer,
                        detail=f'批准删除申请：{comment}',
                        ip_address=_get_client_ip(request),
                    )
                    messages.success(request, '删除申请已批准！')
                else:
                    deletion_req.reject(reviewer=reviewer, comment=comment)
                    OperationLog.log(
                        target_type='deletion_request',
                        target_id=deletion_req.id,
                        action='reject',
                        target_name=deletion_req.place_name.name,
                        operator=reviewer,
                        detail=f'驳回删除申请：{comment}',
                        ip_address=_get_client_ip(request),
                    )
                    messages.success(request, '删除申请已驳回。')
                return redirect('places:deletion_request_detail', pk=deletion_req.pk)
            except ValidationError as e:
                form.add_error(None, str(e))
    else:
        form = DeletionReviewForm()

    context = {
        'deletion_request': deletion_req,
        'form': form,
    }
    return render(request, 'places/deletion_request_review.html', context)


def deletion_request_execute(request, pk):
    deletion_req = get_object_or_404(
        DeletionRequest.objects.select_related('place_name'),
        pk=pk
    )

    if request.method == 'POST':
        try:
            place_name = deletion_req.execute()
            OperationLog.log(
                target_type='deletion_request',
                target_id=deletion_req.id,
                action='delete',
                target_name=place_name,
                detail='执行删除操作',
                ip_address=_get_client_ip(request),
            )
            messages.success(request, f'地名 "{place_name}" 已成功删除')
            return redirect('places:deletion_request_list')
        except ValidationError as e:
            messages.error(request, str(e))

    context = {
        'deletion_request': deletion_req,
    }
    return render(request, 'places/deletion_request_execute.html', context)


def deletion_request_cancel(request, pk):
    deletion_req = get_object_or_404(
        DeletionRequest.objects.select_related('place_name'),
        pk=pk
    )

    if request.method == 'POST':
        try:
            deletion_req.cancel()
            OperationLog.log(
                target_type='deletion_request',
                target_id=deletion_req.id,
                action='update',
                target_name=deletion_req.place_name.name,
                detail='取消删除申请',
                ip_address=_get_client_ip(request),
            )
            messages.success(request, '删除申请已取消')
            return redirect('places:deletion_request_detail', pk=deletion_req.pk)
        except ValidationError as e:
            messages.error(request, str(e))

    context = {
        'deletion_request': deletion_req,
    }
    return render(request, 'places/deletion_request_cancel.html', context)


def annotation_create(request, target_type, target_id):
    if target_type not in dict(Annotation.TARGET_TYPE_CHOICES):
        messages.error(request, '无效的批注目标类型')
        return redirect('places:index')

    if request.method == 'POST':
        form = AnnotationForm(request.POST)
        if form.is_valid():
            annotation = form.save(commit=False)
            annotation.target_type = target_type
            annotation.target_id = target_id
            annotation.save()
            OperationLog.log(
                target_type='annotation',
                target_id=annotation.id,
                action='create',
                target_name=f'{target_type}-{target_id}',
                operator=form.cleaned_data.get('author', ''),
                detail=f'添加批注：{form.cleaned_data["content"][:50]}...',
                ip_address=_get_client_ip(request),
            )
            messages.success(request, '批注添加成功！')

            if target_type == 'place':
                return redirect('places:place_detail', pk=target_id)
            elif target_type == 'literature':
                return redirect('places:literature_detail', pk=target_id)
            elif target_type == 'dispute':
                return redirect('places:dispute_detail', pk=target_id)
            elif target_type == 'deletion_request':
                return redirect('places:deletion_request_detail', pk=target_id)
            else:
                return redirect('places:index')

    return redirect(request.META.get('HTTP_REFERER', 'places:index'))


def annotation_resolve(request, pk):
    annotation = get_object_or_404(Annotation, pk=pk)

    if request.method == 'POST':
        resolver = request.POST.get('resolver', '')
        try:
            annotation.resolve(resolver=resolver)
            OperationLog.log(
                target_type='annotation',
                target_id=annotation.id,
                action='update',
                target_name=f'{annotation.target_type}-{annotation.target_id}',
                operator=resolver,
                detail='标记批注为已解决',
                ip_address=_get_client_ip(request),
            )
            messages.success(request, '批注已标记为已解决')
        except ValidationError as e:
            messages.error(request, str(e))

    return redirect(request.META.get('HTTP_REFERER', 'places:index'))


def operation_log_list(request):
    logs = OperationLog.objects.all().order_by('-created_at')

    target_type = request.GET.get('target_type', '')
    action = request.GET.get('action', '')
    operator = request.GET.get('operator', '')

    if target_type:
        logs = logs.filter(target_type=target_type)

    if action:
        logs = logs.filter(action=action)

    if operator:
        logs = logs.filter(operator__icontains=operator)

    context = {
        'logs': logs[:200],
        'target_type': target_type,
        'action': action,
        'operator': operator,
        'target_type_choices': OperationLog.TARGET_TYPE_CHOICES,
        'action_choices': OperationLog.ACTION_CHOICES,
    }
    return render(request, 'places/operation_log_list.html', context)


def migration_list(request):
    records = MigrationRecord.objects.select_related(
        'place_name'
    ).all().order_by('-created_at')

    search_query = request.GET.get('q', '')
    dynasty = request.GET.get('dynasty', '')
    region = request.GET.get('region', '')
    migration_type = request.GET.get('type', '')
    min_reliability = request.GET.get('min_reliability', '')
    max_reliability = request.GET.get('max_reliability', '')
    status = request.GET.get('status', '')
    has_dispute = request.GET.get('has_dispute', '')

    if search_query:
        records = records.filter(
            Q(title__icontains=search_query) |
            Q(place_name__name__icontains=search_query) |
            Q(migration_reason__icontains=search_query) |
            Q(conclusion__icontains=search_query)
        )

    if dynasty:
        records = records.filter(dynasty__icontains=dynasty)

    if region:
        records = records.filter(region__icontains=region)

    if migration_type:
        records = records.filter(migration_type=migration_type)

    if min_reliability:
        try:
            records = records.filter(reliability__gte=int(min_reliability))
        except ValueError:
            pass

    if max_reliability:
        try:
            records = records.filter(reliability__lte=int(max_reliability))
        except ValueError:
            pass

    if status:
        records = records.filter(status=status)

    if has_dispute == 'yes':
        records = records.filter(has_dispute=True)
    elif has_dispute == 'no':
        records = records.filter(has_dispute=False)

    dynasties = MigrationRecord.objects.values_list(
        'dynasty', flat=True
    ).distinct().order_by('dynasty')
    dynasties = [d for d in dynasties if d]

    regions = MigrationRecord.objects.values_list(
        'region', flat=True
    ).distinct().order_by('region')
    regions = [r for r in regions if r]

    context = {
        'records': records,
        'search_query': search_query,
        'dynasty': dynasty,
        'region': region,
        'migration_type': migration_type,
        'min_reliability': min_reliability,
        'max_reliability': max_reliability,
        'status': status,
        'has_dispute': has_dispute,
        'dynasties': dynasties,
        'regions': regions,
        'migration_type_choices': MigrationRecord.MIGRATION_TYPE_CHOICES,
        'status_choices': MigrationRecord.STATUS_CHOICES,
    }
    return render(request, 'places/migration_list.html', context)


def migration_detail(request, pk):
    record = get_object_or_404(
        MigrationRecord.objects.select_related('place_name'),
        pk=pk
    )
    stages = record.get_stages_sorted()
    evidences = record.evidences.select_related('literature', 'stage').order_by('order_index', 'created_at')
    disputes = record.disputes.select_related('stage').order_by('-created_at')
    versions = record.versions.all()[:10]
    annotations = Annotation.objects.filter(
        target_type='migration', target_id=record.id
    ).order_by('-created_at')

    stages_data = []
    for stage in stages:
        stage_evidences = [e for e in evidences if e.stage_id == stage.id]
        stages_data.append({
            'stage': stage,
            'evidences': stage_evidences,
        })

    general_evidences = [e for e in evidences if e.stage_id is None]

    context = {
        'record': record,
        'stages': stages_data,
        'general_evidences': general_evidences,
        'evidences': evidences,
        'disputes': disputes,
        'versions': versions,
        'annotations': annotations,
        'annotation_form': AnnotationForm(),
        'stages_json': json.dumps([{
            'id': s.id,
            'name': s.stage_name,
            'dynasty': s.dynasty,
            'start_year': s.start_year,
            'end_year': s.end_year,
            'start_year_num': s.start_year_num,
            'end_year_num': s.end_year_num,
            'place_name': s.place_name_text,
            'admin_division': s.administrative_division,
            'region': s.region,
            'longitude': s.longitude,
            'latitude': s.latitude,
            'coordinate_range': s.coordinate_range,
            'description': s.description,
            'reliability': s.reliability,
        } for s in stages], ensure_ascii=False),
    }
    return render(request, 'places/migration_detail.html', context)


def migration_create(request):
    place_id = request.GET.get('place_id', '')
    if request.method == 'POST':
        form = MigrationRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.status = 'draft'
            record.save()
            OperationLog.log(
                target_type='migration',
                target_id=record.id,
                action='create',
                target_name=record.title,
                operator=form.cleaned_data.get('submitter', ''),
                detail='创建时空迁移对照记录（草稿）',
                ip_address=_get_client_ip(request),
            )
            messages.success(request, f'时空迁移对照 "{record.title}" 创建成功！')
            return redirect('places:migration_detail', pk=record.pk)
    else:
        if place_id:
            form = MigrationRecordForm(initial={'place_name': place_id})
        else:
            form = MigrationRecordForm()

    context = {
        'form': form,
        'form_title': '新增时空迁移对照',
    }
    return render(request, 'places/form.html', context)


def migration_edit(request, pk):
    record = get_object_or_404(MigrationRecord, pk=pk)

    if record.status == 'approved':
        messages.error(request, '已审核通过的迁移记录不能编辑')
        return redirect('places:migration_detail', pk=pk)

    if request.method == 'POST':
        form = MigrationRecordEditForm(request.POST, instance=record)
        if form.is_valid():
            record = form.save()
            OperationLog.log(
                target_type='migration',
                target_id=record.id,
                action='update',
                target_name=record.title,
                detail='更新迁移记录信息',
                ip_address=_get_client_ip(request),
            )
            messages.success(request, f'时空迁移对照 "{record.title}" 更新成功！')
            return redirect('places:migration_detail', pk=record.pk)
    else:
        form = MigrationRecordEditForm(instance=record)

    context = {
        'form': form,
        'form_title': '编辑时空迁移对照',
    }
    return render(request, 'places/form.html', context)


def migration_delete(request, pk):
    record = get_object_or_404(
        MigrationRecord.objects.select_related('place_name'),
        pk=pk
    )
    if request.method == 'POST':
        record_title = record.title
        record.delete()
        OperationLog.log(
            target_type='migration',
            target_id=pk,
            action='delete',
            target_name=record_title,
            detail='删除迁移记录',
            ip_address=_get_client_ip(request),
        )
        messages.success(request, f'迁移记录 "{record_title}" 已成功删除')
        return redirect('places:migration_list')

    context = {
        'object': record,
        'object_name': record.title,
        'object_type': '时空迁移对照',
        'can_delete': True,
        'cancel_url': reverse('places:migration_detail', args=[pk]),
    }
    return render(request, 'places/delete_confirm.html', context)


def migration_submit(request, pk):
    record = get_object_or_404(MigrationRecord, pk=pk)

    if request.method == 'POST':
        submitter = request.POST.get('submitter', '')
        try:
            record.submit_for_review(submitter=submitter)
            OperationLog.log(
                target_type='migration',
                target_id=record.id,
                action='submit',
                target_name=record.title,
                operator=submitter,
                detail='提交审核',
                ip_address=_get_client_ip(request),
            )
            messages.success(request, f'迁移记录 "{record.title}" 已提交审核！')
            return redirect('places:migration_detail', pk=pk)
        except ValidationError as e:
            messages.error(request, str(e))

    context = {
        'record': record,
    }
    return render(request, 'places/migration_submit.html', context)


def migration_review_list(request):
    records = MigrationRecord.objects.filter(
        status__in=['submitted']
    ).select_related('place_name').order_by('-submitted_at')

    context = {
        'records': records,
    }
    return render(request, 'places/migration_review_list.html', context)


def migration_review_detail(request, pk):
    record = get_object_or_404(
        MigrationRecord.objects.select_related('place_name'),
        pk=pk
    )
    versions = record.versions.all().order_by('-version_number')

    if request.method == 'POST':
        form = MigrationReviewForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data['action']
            comment = form.cleaned_data['comment']
            reviewer = form.cleaned_data['reviewer']

            try:
                if action == 'approve':
                    record.approve(reviewer=reviewer, comment=comment)
                    OperationLog.log(
                        target_type='migration',
                        target_id=record.id,
                        action='approve',
                        target_name=record.title,
                        operator=reviewer,
                        detail=f'审核通过：{comment}',
                        ip_address=_get_client_ip(request),
                    )
                    messages.success(request, f'迁移记录 "{record.title}" 审核通过！')
                else:
                    record.reject(reviewer=reviewer, comment=comment)
                    OperationLog.log(
                        target_type='migration',
                        target_id=record.id,
                        action='reject',
                        target_name=record.title,
                        operator=reviewer,
                        detail=f'审核驳回：{comment}',
                        ip_address=_get_client_ip(request),
                    )
                    messages.success(request, f'迁移记录 "{record.title}" 已驳回。')
                return redirect('places:migration_review_list')
            except ValidationError as e:
                form.add_error(None, str(e))
    else:
        form = MigrationReviewForm()

    context = {
        'record': record,
        'form': form,
        'versions': versions,
    }
    return render(request, 'places/migration_review_detail.html', context)


def migration_stage_create(request, migration_pk):
    record = get_object_or_404(MigrationRecord, pk=migration_pk)

    if request.method == 'POST':
        form = MigrationStageForm(request.POST)
        if form.is_valid():
            stage = form.save(commit=False)
            stage.migration_record = record
            stage.save()
            OperationLog.log(
                target_type='migration',
                target_id=record.id,
                action='create',
                target_name=record.title,
                detail=f'添加迁移阶段：{stage.stage_name}',
                ip_address=_get_client_ip(request),
            )
            messages.success(request, f'迁移阶段 "{stage.stage_name}" 添加成功！')
            return redirect('places:migration_detail', pk=record.pk)
    else:
        form = MigrationStageForm()

    context = {
        'form': form,
        'record': record,
        'form_title': '添加迁移阶段',
    }
    return render(request, 'places/migration_stage_form.html', context)


def migration_stage_edit(request, pk):
    stage = get_object_or_404(
        MigrationStage.objects.select_related('migration_record'),
        pk=pk
    )
    record = stage.migration_record

    if request.method == 'POST':
        form = MigrationStageForm(request.POST, instance=stage)
        if form.is_valid():
            stage = form.save()
            OperationLog.log(
                target_type='migration',
                target_id=record.id,
                action='update',
                target_name=record.title,
                detail=f'更新迁移阶段：{stage.stage_name}',
                ip_address=_get_client_ip(request),
            )
            messages.success(request, f'迁移阶段 "{stage.stage_name}" 更新成功！')
            return redirect('places:migration_detail', pk=record.pk)
    else:
        form = MigrationStageForm(instance=stage)

    context = {
        'form': form,
        'record': record,
        'stage': stage,
        'form_title': '编辑迁移阶段',
    }
    return render(request, 'places/migration_stage_form.html', context)


def migration_stage_delete(request, pk):
    stage = get_object_or_404(
        MigrationStage.objects.select_related('migration_record'),
        pk=pk
    )
    record = stage.migration_record

    if request.method == 'POST':
        stage_name = stage.stage_name
        stage.delete()
        OperationLog.log(
            target_type='migration',
            target_id=record.id,
            action='delete',
            target_name=record.title,
            detail=f'删除迁移阶段：{stage_name}',
            ip_address=_get_client_ip(request),
        )
        messages.success(request, f'迁移阶段 "{stage_name}" 已成功删除')
        return redirect('places:migration_detail', pk=record.pk)

    context = {
        'object': stage,
        'object_name': stage.stage_name,
        'object_type': '迁移阶段',
        'can_delete': True,
        'cancel_url': reverse('places:migration_detail', args=[record.pk]),
    }
    return render(request, 'places/delete_confirm.html', context)


def migration_evidence_create(request, migration_pk):
    record = get_object_or_404(MigrationRecord, pk=migration_pk)

    if request.method == 'POST':
        form = MigrationEvidenceForm(request.POST)
        form.fields['stage'].queryset = record.stages.all()
        if form.is_valid():
            evidence = form.save(commit=False)
            evidence.migration_record = record
            evidence.save()
            OperationLog.log(
                target_type='migration',
                target_id=record.id,
                action='create',
                target_name=record.title,
                detail=f'添加文献证据：{evidence.literature.title}',
                ip_address=_get_client_ip(request),
            )
            messages.success(request, '文献证据添加成功！')
            return redirect('places:migration_detail', pk=record.pk)
    else:
        form = MigrationEvidenceForm()
        form.fields['stage'].queryset = record.stages.all()

    literatures = Literature.objects.all().order_by('title')
    context = {
        'form': form,
        'record': record,
        'literatures': literatures,
        'form_title': '添加文献证据',
    }
    return render(request, 'places/migration_evidence_form.html', context)


def migration_evidence_delete(request, pk):
    evidence = get_object_or_404(
        MigrationEvidence.objects.select_related('migration_record', 'literature'),
        pk=pk
    )
    record = evidence.migration_record

    if request.method == 'POST':
        lit_title = evidence.literature.title
        evidence.delete()
        OperationLog.log(
            target_type='migration',
            target_id=record.id,
            action='delete',
            target_name=record.title,
            detail=f'删除文献证据：{lit_title}',
            ip_address=_get_client_ip(request),
        )
        messages.success(request, '文献证据已成功删除')
        return redirect('places:migration_detail', pk=record.pk)

    context = {
        'object': evidence,
        'object_name': evidence.literature.title,
        'object_type': '文献证据',
        'can_delete': True,
        'cancel_url': reverse('places:migration_detail', args=[record.pk]),
    }
    return render(request, 'places/delete_confirm.html', context)


def migration_dispute_create(request, migration_pk):
    record = get_object_or_404(MigrationRecord, pk=migration_pk)

    if request.method == 'POST':
        form = MigrationDisputeForm(request.POST)
        form.fields['stage'].queryset = record.stages.all()
        if form.is_valid():
            dispute = form.save(commit=False)
            dispute.migration_record = record
            dispute.save()
            OperationLog.log(
                target_type='migration',
                target_id=record.id,
                action='create',
                target_name=record.title,
                detail=f'添加争议记录：{dispute.title}',
                ip_address=_get_client_ip(request),
            )
            messages.success(request, f'争议记录 "{dispute.title}" 添加成功！')
            return redirect('places:migration_detail', pk=record.pk)
    else:
        form = MigrationDisputeForm()
        form.fields['stage'].queryset = record.stages.all()

    context = {
        'form': form,
        'record': record,
        'form_title': '添加迁移争议',
    }
    return render(request, 'places/migration_dispute_form.html', context)


def migration_dispute_detail(request, pk):
    dispute = get_object_or_404(
        MigrationDispute.objects.select_related('migration_record', 'stage'),
        pk=pk
    )
    annotations = Annotation.objects.filter(
        target_type='dispute', target_id=dispute.id
    ).order_by('-created_at')

    context = {
        'dispute': dispute,
        'record': dispute.migration_record,
        'annotations': annotations,
        'annotation_form': AnnotationForm(),
    }
    return render(request, 'places/migration_dispute_detail.html', context)


def migration_dispute_resolve(request, pk):
    dispute = get_object_or_404(
        MigrationDispute.objects.select_related('migration_record'),
        pk=pk
    )

    if request.method == 'POST':
        resolution = request.POST.get('resolution', '')
        resolver = request.POST.get('resolver', '')
        if not resolution:
            messages.error(request, '解决争议时必须填写解决方案')
        else:
            dispute.status = 'resolved'
            dispute.resolution = resolution
            dispute.resolver = resolver
            dispute.save()
            OperationLog.log(
                target_type='migration',
                target_id=dispute.migration_record.id,
                action='resolve',
                target_name=dispute.migration_record.title,
                detail=f'解决迁移争议：{dispute.title}',
                ip_address=_get_client_ip(request),
            )
            messages.success(request, '争议已解决！')
            return redirect('places:migration_dispute_detail', pk=dispute.pk)

    context = {
        'dispute': dispute,
    }
    return render(request, 'places/migration_dispute_resolve.html', context)


def migration_dispute_reopen(request, pk):
    dispute = get_object_or_404(
        MigrationDispute.objects.select_related('migration_record'),
        pk=pk
    )

    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        reopener = request.POST.get('reopener', '')
        if not reason:
            messages.error(request, '重新开启争议时必须填写理由')
        else:
            dispute.status = 'open'
            dispute.save()
            OperationLog.log(
                target_type='migration',
                target_id=dispute.migration_record.id,
                action='update',
                target_name=dispute.migration_record.title,
                detail=f'重新开启迁移争议：{dispute.title}，理由：{reason[:50]}...',
                ip_address=_get_client_ip(request),
            )
            messages.success(request, '争议已重新开启！')
            return redirect('places:migration_dispute_detail', pk=dispute.pk)

    context = {
        'dispute': dispute,
    }
    return render(request, 'places/migration_dispute_reopen.html', context)


def migration_version_history(request, pk):
    record = get_object_or_404(
        MigrationRecord.objects.select_related('place_name'),
        pk=pk
    )
    versions = record.versions.all().order_by('-version_number')

    context = {
        'record': record,
        'versions': versions,
    }
    return render(request, 'places/migration_version_history.html', context)


def migration_map_data(request, pk):
    record = get_object_or_404(MigrationRecord, pk=pk)
    stages = record.get_stages_sorted()

    stages_data = []
    for idx, stage in enumerate(stages):
        stages_data.append({
            'id': stage.id,
            'index': idx,
            'name': stage.stage_name,
            'dynasty': stage.dynasty,
            'start_year': stage.start_year,
            'end_year': stage.end_year,
            'start_year_num': stage.start_year_num,
            'end_year_num': stage.end_year_num,
            'place_name': stage.place_name_text,
            'admin_division': stage.administrative_division,
            'region': stage.region,
            'longitude': stage.longitude,
            'latitude': stage.latitude,
            'coordinate_range': stage.coordinate_range,
            'description': stage.description,
            'reliability': stage.reliability,
        })

    return JsonResponse({
        'record': {
            'id': record.id,
            'title': record.title,
            'place_name': record.place_name.name,
            'migration_type': record.get_migration_type_display(),
            'reliability': record.reliability,
        },
        'stages': stages_data,
    })
