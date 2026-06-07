from django.test import TestCase, Client
from django.urls import reverse
from django.core.exceptions import ValidationError
from .models import (
    PlaceName, NameRelation, Literature, PlaceNameLiterature,
    Dispute, PlaceNameVersion, ReviewRecord, DeletionRequest,
    Annotation, OperationLog
)
from datetime import date


class PlaceNameReviewWorkflowTests(TestCase):
    def setUp(self):
        self.place = PlaceName.objects.create(
            name='长安',
            alternative_name='西都',
            region='陕西',
            reliability=90,
            review_status='draft',
            start_year='西汉',
            start_year_num=-202,
            end_year='唐代',
            end_year_num=904,
        )
        self.literature = Literature.objects.create(
            title='史记',
            author='司马迁',
            dynasty='西汉',
        )
        PlaceNameLiterature.objects.create(
            place_name=self.place,
            literature=self.literature,
            citation_detail='《史记·高祖本纪》',
        )
        self.client = Client()

    def test_initial_status_is_draft(self):
        self.assertEqual(self.place.review_status, 'draft')

    def test_submit_for_review(self):
        url = reverse('places:place_submit', args=[self.place.pk])
        response = self.client.post(url, {'submitter': '测试员'}, follow=True)
        self.place.refresh_from_db()
        self.assertEqual(self.place.review_status, 'submitted')
        self.assertEqual(self.place.submitter, '测试员')
        self.assertIsNotNone(self.place.submitted_at)

    def test_submit_without_submitter(self):
        url = reverse('places:place_submit', args=[self.place.pk])
        response = self.client.post(url, {}, follow=True)
        self.place.refresh_from_db()
        self.assertEqual(self.place.review_status, 'submitted')

    def test_approve_review(self):
        self.place.review_status = 'submitted'
        self.place.save()

        url = reverse('places:review_detail', args=[self.place.pk])
        response = self.client.post(url, {
            'action': 'approve',
            'comment': '数据准确，审核通过',
            'reviewer': '审核员A'
        }, follow=True)
        self.place.refresh_from_db()
        self.assertEqual(self.place.review_status, 'approved')

    def test_reject_review(self):
        self.place.review_status = 'submitted'
        self.place.save()

        url = reverse('places:review_detail', args=[self.place.pk])
        response = self.client.post(url, {
            'action': 'reject',
            'comment': '数据有误，需要补充来源',
        }, follow=True)
        self.place.refresh_from_db()
        self.assertEqual(self.place.review_status, 'rejected')
        self.assertEqual(self.place.review_comment, '数据有误，需要补充来源')

    def test_cannot_approve_draft_directly(self):
        old_status = self.place.review_status
        url = reverse('places:review_detail', args=[self.place.pk])
        response = self.client.post(url, {
            'action': 'approve',
            'comment': '测试',
        })
        self.place.refresh_from_db()
        self.assertEqual(self.place.review_status, old_status)

    def test_archive_place(self):
        self.place.review_status = 'approved'
        self.place.collation_status = 'completed'
        self.place.save()

        url = reverse('places:place_archive', args=[self.place.pk])
        response = self.client.post(url, {'comment': '完成归档'}, follow=True)
        self.place.refresh_from_db()
        self.assertEqual(self.place.review_status, 'archived')


class PlaceNameVersionTests(TestCase):
    def setUp(self):
        self.place = PlaceName.objects.create(
            name='长安',
            region='陕西',
            reliability=80,
            review_status='draft',
        )

    def test_version_created_on_name_change(self):
        initial_count = PlaceNameVersion.objects.filter(place_name=self.place).count()
        self.place.name = '长安古城'
        self.place.save()

        versions = PlaceNameVersion.objects.filter(place_name=self.place)
        self.assertEqual(versions.count(), initial_count + 1)

        latest = versions.latest('version_number')
        self.assertIn('name', latest.change_fields)

    def test_version_number_increments(self):
        self.place.name = '名称2'
        self.place.save()

        self.place.region = '北京'
        self.place.save()

        versions = PlaceNameVersion.objects.filter(place_name=self.place).order_by('version_number')
        self.assertEqual(versions[0].version_number, 1)
        self.assertEqual(versions[1].version_number, 2)

    def test_version_stores_old_and_new_values(self):
        self.place.name = '新名称'
        self.place.save()

        latest = PlaceNameVersion.objects.filter(place_name=self.place).latest('version_number')
        changes = latest.get_changes_dict()
        self.assertIn('name', changes)
        self.assertEqual(changes['name']['old'], '长安')
        self.assertEqual(changes['name']['new'], '新名称')

    def test_no_version_created_if_no_changes(self):
        initial_count = PlaceNameVersion.objects.filter(place_name=self.place).count()
        self.place.save()
        new_count = PlaceNameVersion.objects.filter(place_name=self.place).count()
        self.assertEqual(initial_count, new_count)


class DeletionRequestWorkflowTests(TestCase):
    def setUp(self):
        self.place = PlaceName.objects.create(
            name='待删除地名',
            region='测试',
            reliability=50,
            review_status='draft',
        )
        self.client = Client()

    def test_create_deletion_request_page_renders(self):
        url = reverse('places:deletion_request_create', args=[self.place.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_approve_deletion_request(self):
        req = DeletionRequest.objects.create(
            place_name=self.place,
            reason='测试删除',
            applicant='测试员',
            status='pending',
        )

        url = reverse('places:deletion_request_review', args=[req.pk])
        response = self.client.post(url, {
            'action': 'approve',
            'comment': '同意删除',
        }, follow=True)
        req.refresh_from_db()
        self.assertEqual(req.status, 'approved')
        self.assertEqual(req.review_comment, '同意删除')

    def test_reject_deletion_request(self):
        req = DeletionRequest.objects.create(
            place_name=self.place,
            reason='测试删除',
            applicant='测试员',
            status='pending',
        )

        url = reverse('places:deletion_request_review', args=[req.pk])
        response = self.client.post(url, {
            'action': 'reject',
            'comment': '数据有效，不予删除',
        }, follow=True)
        req.refresh_from_db()
        self.assertEqual(req.status, 'rejected')

    def test_execute_deletion(self):
        req = DeletionRequest.objects.create(
            place_name=self.place,
            reason='测试删除',
            applicant='测试员',
            status='approved',
        )

        place_pk = self.place.pk
        url = reverse('places:deletion_request_execute', args=[req.pk])
        response = self.client.post(url, {}, follow=True)

        self.assertFalse(PlaceName.objects.filter(pk=place_pk).exists())
        req.refresh_from_db()
        self.assertEqual(req.status, 'completed')

    def test_cancel_deletion_request(self):
        req = DeletionRequest.objects.create(
            place_name=self.place,
            reason='测试删除',
            applicant='测试员',
            status='pending',
        )

        url = reverse('places:deletion_request_cancel', args=[req.pk])
        response = self.client.post(url, {}, follow=True)
        req.refresh_from_db()
        self.assertEqual(req.status, 'cancelled')

    def test_cannot_delete_place_with_relations(self):
        place2 = PlaceName.objects.create(
            name='关联地名',
            region='测试',
            reliability=60,
        )
        NameRelation.objects.create(
            name_a=self.place,
            name_b=place2,
            relation_type='alias',
            reliability=70,
        )
        self.place.refresh_from_db()

        self.assertFalse(self.place.can_delete())

    def test_can_delete_place_without_relations(self):
        self.assertTrue(self.place.can_delete())


class DisputeWorkflowTests(TestCase):
    def setUp(self):
        self.place = PlaceName.objects.create(
            name='争议地名',
            region='测试',
            reliability=70,
        )
        self.dispute = Dispute.objects.create(
            place_name=self.place,
            title='名称准确性争议',
            content='对该地名的出处有疑问',
            proposer='研究员A',
            status='open',
        )
        self.client = Client()

    def test_initial_status_is_open(self):
        self.assertEqual(self.dispute.status, 'open')
        self.assertEqual(self.dispute.reopen_count, 0)

    def test_resolve_dispute(self):
        url = reverse('places:dispute_resolve', args=[self.dispute.pk])
        response = self.client.post(url, {
            'resolution': '已核实，数据准确',
            'resolution_type': 'evidence',
        }, follow=True)
        self.dispute.refresh_from_db()
        self.assertEqual(self.dispute.status, 'resolved')
        self.assertEqual(self.dispute.resolution, '已核实，数据准确')
        self.assertEqual(self.dispute.resolution_type, 'evidence')
        self.assertIsNotNone(self.dispute.resolved_date)

    def test_reject_dispute(self):
        url = reverse('places:dispute_reject', args=[self.dispute.pk])
        response = self.client.post(url, {
            'reason': '争议不成立，依据充分',
        }, follow=True)
        self.dispute.refresh_from_db()
        self.assertEqual(self.dispute.status, 'rejected')

    def test_reopen_dispute(self):
        self.dispute.status = 'resolved'
        self.dispute.resolution = '临时解决'
        self.dispute.save()

        url = reverse('places:dispute_reopen', args=[self.dispute.pk])
        response = self.client.post(url, {
            'reason': '发现新的证据',
        }, follow=True)
        self.dispute.refresh_from_db()
        self.assertEqual(self.dispute.status, 'open')
        self.assertEqual(self.dispute.reopen_count, 1)

    def test_place_has_unresolved_disputes(self):
        self.assertTrue(self.place.has_unresolved_disputes())

    def test_place_no_unresolved_disputes(self):
        self.dispute.status = 'resolved'
        self.dispute.save()
        self.place.refresh_from_db()
        self.assertFalse(self.place.has_unresolved_disputes())

    def test_reopen_multiple_times(self):
        self.dispute.status = 'resolved'
        self.dispute.resolution = '第一次解决'
        self.dispute.save()

        for i in range(3):
            url = reverse('places:dispute_reopen', args=[self.dispute.pk])
            self.client.post(url, {'reason': '重新开启'}, follow=True)

            self.dispute.refresh_from_db()
            self.assertEqual(self.dispute.status, 'open')

            self.dispute.status = 'resolved'
            self.dispute.resolution = '解决' + str(i)
            self.dispute.save()

        self.dispute.refresh_from_db()
        self.assertEqual(self.dispute.reopen_count, 3)


class AnnotationTests(TestCase):
    def setUp(self):
        self.place = PlaceName.objects.create(
            name='批注测试',
            region='测试',
            reliability=70,
        )
        self.client = Client()

    def test_create_annotation(self):
        url = reverse('places:annotation_create', args=['place', self.place.pk])
        response = self.client.post(url, {
            'content': '这里需要补充更多文献',
            'author': '研究员B',
        }, follow=True)

        annotation = Annotation.objects.filter(
            target_type='place',
            target_id=self.place.pk
        ).first()
        self.assertIsNotNone(annotation)
        self.assertEqual(annotation.content, '这里需要补充更多文献')
        self.assertEqual(annotation.author, '研究员B')
        self.assertFalse(annotation.is_resolved)

    def test_resolve_annotation(self):
        annotation = Annotation.objects.create(
            target_type='place',
            target_id=self.place.pk,
            content='测试批注',
            author='测试员',
        )

        url = reverse('places:annotation_resolve', args=[annotation.pk])
        response = self.client.post(url, {}, follow=True)
        annotation.refresh_from_db()
        self.assertTrue(annotation.is_resolved)


class OperationLogTests(TestCase):
    def setUp(self):
        self.place = PlaceName.objects.create(
            name='日志测试',
            region='测试',
            reliability=80,
            review_status='draft',
        )
        self.literature = Literature.objects.create(
            title='测试文献',
            author='测试作者',
        )
        PlaceNameLiterature.objects.create(
            place_name=self.place,
            literature=self.literature,
            citation_detail='测试引用',
        )
        self.client = Client()

    def test_operation_log_created_on_submit(self):
        initial_count = OperationLog.objects.count()
        url = reverse('places:place_submit', args=[self.place.pk])
        self.client.post(url, {'submitter': '测试员'}, follow=True)

        logs = OperationLog.objects.filter(
            target_type='place',
            target_id=self.place.pk,
            action='submit',
        )
        self.assertTrue(logs.exists())

    def test_operation_log_ip_recorded(self):
        url = reverse('places:place_submit', args=[self.place.pk])
        self.client.post(url, {'submitter': '测试员'}, REMOTE_ADDR='127.0.0.1', follow=True)

        log = OperationLog.objects.filter(
            target_type='place',
            target_id=self.place.pk,
            action='submit',
        ).latest('created_at')
        self.assertEqual(log.ip_address, '127.0.0.1')

    def test_log_class_method(self):
        log = OperationLog.log(
            target_type='place',
            target_id=self.place.pk,
            action='update',
            target_name=self.place.name,
            operator='测试员',
            detail='测试日志',
            ip_address='192.168.1.1',
        )
        self.assertEqual(log.target_type, 'place')
        self.assertEqual(log.action, 'update')
        self.assertEqual(log.ip_address, '192.168.1.1')


class NameRelationStatusTests(TestCase):
    def setUp(self):
        self.place_a = PlaceName.objects.create(
            name='地名A',
            region='测试',
            reliability=80,
        )
        self.place_b = PlaceName.objects.create(
            name='地名B',
            region='测试',
            reliability=75,
        )

    def test_default_status_is_proposed(self):
        relation = NameRelation.objects.create(
            name_a=self.place_a,
            name_b=self.place_b,
            relation_type='alias',
            reliability=70,
        )
        self.assertEqual(relation.status, 'proposed')

    def test_relation_status_choices(self):
        relation = NameRelation.objects.create(
            name_a=self.place_a,
            name_b=self.place_b,
            relation_type='alias',
            reliability=70,
            status='confirmed',
        )
        self.assertEqual(relation.get_status_display(), '已确认')

        relation.status = 'disputed'
        relation.save()
        self.assertEqual(relation.get_status_display(), '有争议')

        relation.status = 'rejected'
        relation.save()
        self.assertEqual(relation.get_status_display(), '已驳回')

    def test_cannot_relate_to_self(self):
        with self.assertRaises(ValidationError):
            relation = NameRelation(
                name_a=self.place_a,
                name_b=self.place_a,
                relation_type='alias',
                reliability=70,
            )
            relation.full_clean()

    def test_reliability_must_be_between_0_and_100(self):
        with self.assertRaises(ValidationError):
            relation = NameRelation(
                name_a=self.place_a,
                name_b=self.place_b,
                relation_type='alias',
                reliability=150,
            )
            relation.full_clean()


class LiteratureCitationChainTests(TestCase):
    def setUp(self):
        self.literature1 = Literature.objects.create(
            title='史记',
            author='司马迁',
            dynasty='西汉',
        )
        self.literature2 = Literature.objects.create(
            title='汉书',
            author='班固',
            dynasty='东汉',
        )
        self.place1 = PlaceName.objects.create(
            name='长安',
            region='陕西',
            reliability=90,
        )
        self.place2 = PlaceName.objects.create(
            name='洛阳',
            region='河南',
            reliability=85,
        )

        PlaceNameLiterature.objects.create(
            place_name=self.place1,
            literature=self.literature1,
            citation_detail='见《史记·高祖本纪》',
        )
        PlaceNameLiterature.objects.create(
            place_name=self.place1,
            literature=self.literature2,
            citation_detail='见《汉书·地理志》',
        )
        PlaceNameLiterature.objects.create(
            place_name=self.place2,
            literature=self.literature2,
        )

    def test_get_cited_places(self):
        places = self.literature1.get_cited_places()
        self.assertEqual(places.count(), 1)
        self.assertEqual(places.first(), self.place1)

    def test_citation_chain(self):
        chain = self.literature1.get_citation_chain()
        self.assertTrue(len(chain) > 0)

        first_item = chain[0]
        self.assertIn('literature', first_item)
        self.assertIn('depth', first_item)
        self.assertEqual(first_item['literature'].pk, self.literature1.pk)
        self.assertEqual(first_item['depth'], 0)

    def test_citation_chain_includes_other_literatures(self):
        chain = self.literature1.get_citation_chain()
        lit_pks = [item['literature'].pk for item in chain]
        self.assertIn(self.literature1.pk, lit_pks)
        self.assertIn(self.literature2.pk, lit_pks)


class ReviewRecordTests(TestCase):
    def setUp(self):
        self.place = PlaceName.objects.create(
            name='审核记录测试',
            region='测试',
            reliability=80,
            review_status='submitted',
        )

    def test_create_review_record(self):
        record = ReviewRecord.objects.create(
            place_name=self.place,
            action='approve',
            operator='审核员',
            comment='审核通过',
        )
        self.assertEqual(record.get_action_display(), '审核通过')
        self.assertEqual(record.operator, '审核员')


class PlaceListFilterTests(TestCase):
    def setUp(self):
        self.place1 = PlaceName.objects.create(
            name='长安',
            region='陕西',
            reliability=90,
            review_status='approved',
        )
        self.place2 = PlaceName.objects.create(
            name='洛阳',
            region='河南',
            reliability=80,
            review_status='draft',
        )
        self.place3 = PlaceName.objects.create(
            name='开封',
            region='河南',
            reliability=70,
            review_status='submitted',
        )
        self.client = Client()

    def test_filter_by_review_status(self):
        url = reverse('places:place_list') + '?review_status=approved'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '长安')

    def test_filter_by_region(self):
        url = reverse('places:place_list') + '?region=河南'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '洛阳')
        self.assertContains(response, '开封')


class GraphDataFilterTests(TestCase):
    def setUp(self):
        self.place1 = PlaceName.objects.create(
            name='长安',
            region='陕西',
            reliability=90,
            review_status='approved',
            start_year_num=-202,
            end_year_num=904,
        )
        self.place2 = PlaceName.objects.create(
            name='洛阳',
            region='河南',
            reliability=80,
            review_status='approved',
            start_year_num=-770,
            end_year_num=1279,
        )
        self.relation = NameRelation.objects.create(
            name_a=self.place1,
            name_b=self.place2,
            relation_type='alias',
            reliability=85,
            status='confirmed',
        )
        self.client = Client()

    def test_graph_data_loads(self):
        url = reverse('places:graph_data')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('elements', data)
        self.assertTrue(len(data['elements']) > 0)

    def test_graph_filter_by_relation_status(self):
        self.relation.status = 'disputed'
        self.relation.save()

        url = reverse('places:graph_data') + '?relation_status=confirmed'
        response = self.client.get(url)
        data = response.json()
        edges = [e for e in data['elements'] if e.get('group') == 'edges']
        self.assertEqual(len(edges), 0)

    def test_graph_filter_by_year_range(self):
        url = reverse('places:graph_data') + '?start_year_num=-300&end_year_num=0'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_graph_filter_by_review_status(self):
        url = reverse('places:graph_data') + '?review_status=draft'
        response = self.client.get(url)
        data = response.json()
        nodes = [n for n in data['elements'] if n.get('group') == 'nodes']
        self.assertEqual(len(nodes), 0)


class BusinessValidationTests(TestCase):
    def test_reliability_percentage_validation(self):
        place = PlaceName(
            name='测试',
            region='测试',
            reliability=150,
        )
        with self.assertRaises(ValidationError):
            place.full_clean()

    def test_required_name_field(self):
        place = PlaceName(region='测试', reliability=70)
        with self.assertRaises(ValidationError):
            place.full_clean()

    def test_review_status_valid_choices(self):
        valid_statuses = ['draft', 'submitted', 'reviewing', 'approved', 'rejected', 'archived']
        for status in valid_statuses:
            place = PlaceName(
                name='测试' + status,
                region='测试',
                reliability=70,
                review_status=status,
            )
            self.assertEqual(place.review_status, status)

    def test_dispute_resolve_requires_resolution(self):
        place = PlaceName.objects.create(name='测试', region='测试', reliability=70)
        dispute = Dispute.objects.create(
            place_name=place,
            title='测试争议',
            content='测试内容',
        )
        with self.assertRaises(ValidationError):
            dispute.resolve(resolution='')

    def test_dispute_cannot_resolve_when_already_resolved(self):
        place = PlaceName.objects.create(name='测试', region='测试', reliability=70)
        dispute = Dispute.objects.create(
            place_name=place,
            title='测试争议',
            content='测试内容',
            status='resolved',
            resolution='已解决',
        )
        with self.assertRaises(ValidationError):
            dispute.resolve(resolution='再次解决')


class ViewAccessTests(TestCase):
    def setUp(self):
        self.place = PlaceName.objects.create(
            name='测试地名',
            region='测试',
            reliability=70,
            review_status='draft',
        )
        self.literature = Literature.objects.create(
            title='测试文献',
            author='测试',
        )
        self.client = Client()

    def test_review_list_accessible(self):
        url = reverse('places:review_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_deletion_request_list_accessible(self):
        url = reverse('places:deletion_request_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_operation_log_list_accessible(self):
        url = reverse('places:operation_log_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_version_history_accessible(self):
        url = reverse('places:version_history', args=[self.place.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_literature_detail_accessible(self):
        url = reverse('places:literature_detail', args=[self.literature.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_dispute_list_accessible(self):
        url = reverse('places:dispute_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_place_detail_accessible(self):
        url = reverse('places:place_detail', args=[self.place.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_graph_page_accessible(self):
        url = reverse('places:graph')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_place_edit_accessible(self):
        url = reverse('places:place_edit', args=[self.place.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
