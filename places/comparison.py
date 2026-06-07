import json
from django.db.models import Q, Count
from .models import (
    PlaceName,
    Literature,
    PlaceNameLiterature,
    NameRelation,
    ComparisonDoubt,
    CollationTask,
)


def _get_place_literature_map():
    queryset = PlaceNameLiterature.objects.select_related(
        'place_name', 'literature'
    ).all()
    result = {}
    for rel in queryset:
        pid = rel.place_name_id
        if pid not in result:
            result[pid] = []
        result[pid].append({
            'literature_id': rel.literature_id,
            'literature_title': rel.literature.title,
            'literature_dynasty': rel.literature.dynasty,
            'citation_detail': rel.citation_detail,
        })
    return result


def _haversine_distance(lat1, lon1, lat2, lon2):
    import math
    R = 6371.0
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def detect_same_name_diff_place(comparison, place_lit_map):
    doubts = []
    places = PlaceName.objects.all().prefetch_related('literatures')

    name_groups = {}
    for place in places:
        name = place.name.strip()
        if not name:
            continue
        if name not in name_groups:
            name_groups[name] = []
        name_groups[name].append(place)

    for name, group in name_groups.items():
        if len(group) < 2:
            continue

        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                place_a = group[i]
                place_b = group[j]

                region_diff = (
                    place_a.region
                    and place_b.region
                    and place_a.region != place_b.region
                )

                coord_diff = False
                distance = 0
                if (place_a.latitude is not None and place_a.longitude is not None
                        and place_b.latitude is not None and place_b.longitude is not None):
                    distance = _haversine_distance(
                        place_a.latitude, place_a.longitude,
                        place_b.latitude, place_b.longitude
                    )
                    if distance > 50:
                        coord_diff = True

                if not (region_diff or coord_diff):
                    continue

                severity = 'high' if (region_diff and coord_diff) else 'medium'
                if distance > 500:
                    severity = 'high'

                lit_a = place_lit_map.get(place_a.id, [])
                lit_b = place_lit_map.get(place_b.id, [])

                evidence = []
                for lit in lit_a:
                    evidence.append({
                        'place_id': place_a.id,
                        'place_name': place_a.name,
                        'literature': lit['literature_title'],
                        'dynasty': lit['literature_dynasty'],
                        'region': place_a.region,
                        'coord': f'{place_a.longitude}, {place_a.latitude}' if place_a.longitude else '',
                    })
                for lit in lit_b:
                    evidence.append({
                        'place_id': place_b.id,
                        'place_name': place_b.name,
                        'literature': lit['literature_title'],
                        'dynasty': lit['literature_dynasty'],
                        'region': place_b.region,
                        'coord': f'{place_b.longitude}, {place_b.latitude}' if place_b.longitude else '',
                    })

                conflict_detail = {
                    'place_a': {
                        'id': place_a.id,
                        'name': place_a.name,
                        'region': place_a.region,
                        'longitude': place_a.longitude,
                        'latitude': place_a.latitude,
                    },
                    'place_b': {
                        'id': place_b.id,
                        'name': place_b.name,
                        'region': place_b.region,
                        'longitude': place_b.longitude,
                        'latitude': place_b.latitude,
                    },
                    'distance_km': round(distance, 2),
                    'region_diff': region_diff,
                    'coord_diff': coord_diff,
                }

                description_parts = [f'地名 "{name}" 在不同文献中指向不同地点。']
                if region_diff:
                    description_parts.append(
                        f'地区记载不同：{place_a.region or "（空）"} vs {place_b.region or "（空）"}'
                    )
                if coord_diff:
                    description_parts.append(
                        f'坐标距离约 {round(distance, 2)} 公里'
                    )

                doubt = ComparisonDoubt(
                    comparison=comparison,
                    doubt_type='same_name_diff_place',
                    severity=severity,
                    title=f'同名异地：{name}',
                    description='\n'.join(description_parts),
                    conflict_detail=conflict_detail,
                    evidence_data=evidence,
                    place_a=place_a,
                    place_b=place_b,
                )
                doubts.append(doubt)

    return doubts


def detect_diff_name_same_place(comparison, place_lit_map):
    doubts = []
    places = PlaceName.objects.filter(
        Q(longitude__isnull=False) & Q(latitude__isnull=False)
    ).prefetch_related('literatures')

    places_list = list(places)
    threshold_km = 20

    existing_relations = set()
    for rel in NameRelation.objects.filter(status='confirmed').all():
        pair = tuple(sorted([rel.name_a_id, rel.name_b_id]))
        existing_relations.add(pair)

    for i in range(len(places_list)):
        for j in range(i + 1, len(places_list)):
            place_a = places_list[i]
            place_b = places_list[j]

            if place_a.name == place_b.name:
                continue

            pair = tuple(sorted([place_a.id, place_b.id]))
            if pair in existing_relations:
                continue

            distance = _haversine_distance(
                place_a.latitude, place_a.longitude,
                place_b.latitude, place_b.longitude
            )

            if distance > threshold_km:
                continue

            region_same = (
                place_a.region
                and place_b.region
                and place_a.region == place_b.region
            )

            severity = 'medium'
            if distance < 5:
                severity = 'high'
            elif distance > 15:
                severity = 'low'

            if region_same and severity == 'medium':
                severity = 'high'

            lit_a = place_lit_map.get(place_a.id, [])
            lit_b = place_lit_map.get(place_b.id, [])

            evidence = []
            for lit in lit_a:
                evidence.append({
                    'place_id': place_a.id,
                    'place_name': place_a.name,
                    'literature': lit['literature_title'],
                    'dynasty': lit['literature_dynasty'],
                    'region': place_a.region,
                    'coord': f'{place_a.longitude}, {place_a.latitude}',
                })
            for lit in lit_b:
                evidence.append({
                    'place_id': place_b.id,
                    'place_name': place_b.name,
                    'literature': lit['literature_title'],
                    'dynasty': lit['literature_dynasty'],
                    'region': place_b.region,
                    'coord': f'{place_b.longitude}, {place_b.latitude}',
                })

            conflict_detail = {
                'place_a': {
                    'id': place_a.id,
                    'name': place_a.name,
                    'alternative_name': place_a.alternative_name,
                    'region': place_a.region,
                    'longitude': place_a.longitude,
                    'latitude': place_a.latitude,
                },
                'place_b': {
                    'id': place_b.id,
                    'name': place_b.name,
                    'alternative_name': place_b.alternative_name,
                    'region': place_b.region,
                    'longitude': place_b.longitude,
                    'latitude': place_b.latitude,
                },
                'distance_km': round(distance, 2),
                'region_same': region_same,
            }

            description = (
                f'地名 "{place_a.name}" 与 "{place_b.name}" 坐标接近（约 {round(distance, 2)} 公里），'
                f'可能为同一地点的不同名称。'
            )
            if region_same:
                description += f'两地均属于 {place_a.region}。'

            doubt = ComparisonDoubt(
                comparison=comparison,
                doubt_type='diff_name_same_place',
                severity=severity,
                title=f'异名同地：{place_a.name} ↔ {place_b.name}',
                description=description,
                conflict_detail=conflict_detail,
                evidence_data=evidence,
                place_a=place_a,
                place_b=place_b,
            )
            doubts.append(doubt)

    return doubts


def detect_year_conflict(comparison, place_lit_map):
    doubts = []

    places = PlaceName.objects.filter(
        Q(start_year_num__isnull=False) | Q(end_year_num__isnull=False)
    ).prefetch_related('literatures')

    for place in places:
        lit_rels = PlaceNameLiterature.objects.filter(
            place_name=place
        ).select_related('literature')

        if lit_rels.count() < 2:
            continue

        year_info_list = []
        for rel in lit_rels:
            lit = rel.literature
            year_info_list.append({
                'literature_id': lit.id,
                'literature_title': lit.title,
                'dynasty': lit.dynasty,
                'citation_detail': rel.citation_detail,
            })

        has_conflict = False
        conflict_type = []
        description_parts = [f'地名 "{place.name}" 在不同文献中的年代记载存在冲突。']

        if place.start_year and place.end_year:
            if (place.start_year_num is not None
                    and place.end_year_num is not None
                    and place.start_year_num > place.end_year_num):
                has_conflict = True
                conflict_type.append('起止年颠倒')
                description_parts.append(
                    f'始见年({place.start_year})晚于废止年({place.end_year})'
                )

        dynasties = set()
        for info in year_info_list:
            if info['dynasty']:
                dynasties.add(info['dynasty'])

        if len(dynasties) >= 2:
            has_conflict = True
            conflict_type.append('朝代记载不同')
            description_parts.append(f'涉及朝代：{"、".join(dynasties)}')

        if not has_conflict:
            continue

        severity = 'high' if '起止年颠倒' in conflict_type else 'medium'

        evidence = []
        for info in year_info_list:
            evidence.append({
                'place_id': place.id,
                'place_name': place.name,
                'literature': info['literature_title'],
                'dynasty': info['dynasty'],
                'start_year': place.start_year,
                'end_year': place.end_year,
                'citation_detail': info['citation_detail'],
            })

        conflict_detail = {
            'place_id': place.id,
            'place_name': place.name,
            'start_year': place.start_year,
            'end_year': place.end_year,
            'start_year_num': place.start_year_num,
            'end_year_num': place.end_year_num,
            'conflict_types': conflict_type,
            'dynasties': list(dynasties),
        }

        doubt = ComparisonDoubt(
            comparison=comparison,
            doubt_type='year_conflict',
            severity=severity,
            title=f'年代冲突：{place.name}',
            description='\n'.join(description_parts),
            conflict_detail=conflict_detail,
            evidence_data=evidence,
            place_a=place,
        )
        doubts.append(doubt)

    return doubts


def detect_region_conflict(comparison, place_lit_map):
    doubts = []

    name_groups = {}
    all_places = PlaceName.objects.all().prefetch_related('literatures')

    for place in all_places:
        name = place.name.strip()
        if not name or not place.region:
            continue
        if name not in name_groups:
            name_groups[name] = []
        name_groups[name].append(place)

    for name, group in name_groups.items():
        if len(group) < 2:
            continue

        regions = set(p.region for p in group if p.region)
        if len(regions) < 2:
            continue

        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                place_a = group[i]
                place_b = group[j]

                if place_a.region == place_b.region:
                    continue

                lit_a = place_lit_map.get(place_a.id, [])
                lit_b = place_lit_map.get(place_b.id, [])

                if not lit_a or not lit_b:
                    continue

                evidence = []
                for lit in lit_a:
                    evidence.append({
                        'place_id': place_a.id,
                        'place_name': place_a.name,
                        'literature': lit['literature_title'],
                        'dynasty': lit['literature_dynasty'],
                        'region': place_a.region,
                    })
                for lit in lit_b:
                    evidence.append({
                        'place_id': place_b.id,
                        'place_name': place_b.name,
                        'literature': lit['literature_title'],
                        'dynasty': lit['literature_dynasty'],
                        'region': place_b.region,
                    })

                conflict_detail = {
                    'place_a': {
                        'id': place_a.id,
                        'name': place_a.name,
                        'region': place_a.region,
                    },
                    'place_b': {
                        'id': place_b.id,
                        'name': place_b.name,
                        'region': place_b.region,
                    },
                    'regions': list(regions),
                }

                description = (
                    f'地名 "{name}" 的行政归属记载存在冲突：'
                    f'{place_a.region} vs {place_b.region}'
                )

                doubt = ComparisonDoubt(
                    comparison=comparison,
                    doubt_type='region_conflict',
                    severity='medium',
                    title=f'行政归属冲突：{name}',
                    description=description,
                    conflict_detail=conflict_detail,
                    evidence_data=evidence,
                    place_a=place_a,
                    place_b=place_b,
                )
                doubts.append(doubt)

    return doubts


def detect_coordinate_conflict(comparison, place_lit_map):
    doubts = []

    places_with_coord = PlaceName.objects.filter(
        Q(longitude__isnull=False) & Q(latitude__isnull=False)
    ).prefetch_related('literatures')

    name_groups = {}
    for place in places_with_coord:
        name = place.name.strip()
        if not name:
            continue
        if name not in name_groups:
            name_groups[name] = []
        name_groups[name].append(place)

    for name, group in name_groups.items():
        if len(group) < 2:
            continue

        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                place_a = group[i]
                place_b = group[j]

                distance = _haversine_distance(
                    place_a.latitude, place_a.longitude,
                    place_b.latitude, place_b.longitude
                )

                if distance < 10:
                    continue

                lit_a = place_lit_map.get(place_a.id, [])
                lit_b = place_lit_map.get(place_b.id, [])

                if not lit_a or not lit_b:
                    continue

                severity = 'medium'
                if distance > 100:
                    severity = 'high'
                elif distance < 30:
                    severity = 'low'

                evidence = []
                for lit in lit_a:
                    evidence.append({
                        'place_id': place_a.id,
                        'place_name': place_a.name,
                        'literature': lit['literature_title'],
                        'dynasty': lit['literature_dynasty'],
                        'longitude': place_a.longitude,
                        'latitude': place_a.latitude,
                    })
                for lit in lit_b:
                    evidence.append({
                        'place_id': place_b.id,
                        'place_name': place_b.name,
                        'literature': lit['literature_title'],
                        'dynasty': lit['literature_dynasty'],
                        'longitude': place_b.longitude,
                        'latitude': place_b.latitude,
                    })

                conflict_detail = {
                    'place_a': {
                        'id': place_a.id,
                        'name': place_a.name,
                        'longitude': place_a.longitude,
                        'latitude': place_a.latitude,
                    },
                    'place_b': {
                        'id': place_b.id,
                        'name': place_b.name,
                        'longitude': place_b.longitude,
                        'latitude': place_b.latitude,
                    },
                    'distance_km': round(distance, 2),
                }

                description = (
                    f'同名地名 "{name}" 的坐标记载差异较大，'
                    f'两地相距约 {round(distance, 2)} 公里。'
                )

                doubt = ComparisonDoubt(
                    comparison=comparison,
                    doubt_type='coordinate_conflict',
                    severity=severity,
                    title=f'坐标冲突：{name}',
                    description=description,
                    conflict_detail=conflict_detail,
                    evidence_data=evidence,
                    place_a=place_a,
                    place_b=place_b,
                )
                doubts.append(doubt)

    return doubts


def detect_reliability_abnormal(comparison, place_lit_map):
    doubts = []

    all_places = PlaceName.objects.all().prefetch_related('literatures')

    lit_count_map = {}
    for place in all_places:
        lit_count = place.literatures.count()
        lit_count_map[place.id] = lit_count

    avg_reliability = 50
    reliabilities = [p.reliability for p in all_places if p.reliability is not None]
    if reliabilities:
        avg_reliability = sum(reliabilities) / len(reliabilities)

    low_threshold = max(20, avg_reliability * 0.4)
    high_threshold = min(95, avg_reliability * 1.6)

    for place in all_places:
        lit_count = lit_count_map.get(place.id, 0)

        issues = []
        severity = 'low'

        if place.reliability is not None and place.reliability < low_threshold:
            issues.append(f'可信度偏低（{place.reliability}分，低于阈值{int(low_threshold)}分）')
            severity = 'medium'

        if place.reliability is not None and place.reliability > high_threshold:
            if lit_count < 2:
                issues.append(f'可信度偏高但文献依据不足（{place.reliability}分，仅{lit_count}条文献）')
                severity = 'low'

        if lit_count == 0:
            issues.append('无文献出处支撑')
            severity = 'high'

        if not issues:
            continue

        lit_list = place_lit_map.get(place.id, [])
        evidence = []
        for lit in lit_list:
            evidence.append({
                'place_id': place.id,
                'place_name': place.name,
                'literature': lit['literature_title'],
                'dynasty': lit['literature_dynasty'],
                'citation_detail': lit['citation_detail'],
            })

        conflict_detail = {
            'place_id': place.id,
            'place_name': place.name,
            'reliability': place.reliability,
            'literature_count': lit_count,
            'avg_reliability': round(avg_reliability, 2),
            'low_threshold': round(low_threshold, 2),
            'high_threshold': round(high_threshold, 2),
            'issues': issues,
        }

        description = f'地名 "{place.name}" 存在可信度异常：' + '；'.join(issues)

        doubt = ComparisonDoubt(
            comparison=comparison,
            doubt_type='reliability_abnormal',
            severity=severity,
            title=f'可信度异常：{place.name}',
            description=description,
            conflict_detail=conflict_detail,
            evidence_data=evidence,
            place_a=place,
        )
        doubts.append(doubt)

    return doubts


def run_full_comparison(comparison):
    place_lit_map = _get_place_literature_map()
    total_places = PlaceName.objects.count()

    detectors = [
        ('同名异地', detect_same_name_diff_place),
        ('异名同地', detect_diff_name_same_place),
        ('年代冲突', detect_year_conflict),
        ('行政归属冲突', detect_region_conflict),
        ('坐标冲突', detect_coordinate_conflict),
        ('可信度异常', detect_reliability_abnormal),
    ]

    all_doubts = []
    for name, detector in detectors:
        try:
            doubts = detector(comparison, place_lit_map)
            all_doubts.extend(doubts)
        except Exception as e:
            print(f'Error in {name} detector: {e}')

    ComparisonDoubt.objects.bulk_create(all_doubts, batch_size=100)

    for doubt in all_doubts:
        if doubt.status == 'pending':
            try:
                task_title = f'核查疑点：{doubt.title}'
                task_desc = (
                    f'疑点类型：{doubt.get_doubt_type_display()}\n'
                    f'严重程度：{doubt.get_severity_display()}\n'
                    f'疑点描述：{doubt.description}\n\n'
                    f'请核查该疑点，确认是否为真正的冲突，并给出处理结论。'
                )

                CollationTask.objects.create(
                    doubt=doubt,
                    task_type='verify_doubt',
                    priority=doubt.severity if doubt.severity in ['urgent', 'high', 'medium', 'low'] else 'medium',
                    title=task_title,
                    description=task_desc,
                    place_name=doubt.place_a,
                    status='pending',
                )
            except Exception as e:
                print(f'Error creating collation task for doubt {doubt.id}: {e}')

    total_tasks = CollationTask.objects.filter(comparison=comparison).count()

    return {
        'total_places': total_places,
        'total_doubts': len(all_doubts),
        'total_tasks': total_tasks,
        'by_type': {
            dt: len([d for d in all_doubts if d.doubt_type == dt])
            for dt, _ in ComparisonDoubt.DOUBT_TYPE_CHOICES
        },
        'by_severity': {
            sev: len([d for d in all_doubts if d.severity == sev])
            for sev, _ in ComparisonDoubt.SEVERITY_CHOICES
        },
    }
