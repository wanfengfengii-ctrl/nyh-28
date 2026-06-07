from django.urls import path
from . import views

app_name = 'places'

urlpatterns = [
    path('', views.index, name='index'),
    path('places/', views.place_list, name='place_list'),
    path('places/new/', views.place_create, name='place_create'),
    path('places/<int:pk>/', views.place_detail, name='place_detail'),
    path('places/<int:pk>/edit/', views.place_edit, name='place_edit'),
    path('places/<int:pk>/submit/', views.place_submit, name='place_submit'),
    path('places/<int:pk>/archive/', views.place_archive, name='place_archive'),
    path('places/<int:pk>/delete/', views.place_delete, name='place_delete'),
    path('places/<int:pk>/versions/', views.version_history, name='version_history'),

    path('reviews/', views.review_list, name='review_list'),
    path('reviews/<int:pk>/', views.review_detail, name='review_detail'),

    path('relations/', views.relation_list, name='relation_list'),
    path('relations/new/', views.relation_create, name='relation_create'),
    path('relations/<int:pk>/delete/', views.relation_delete, name='relation_delete'),

    path('graph/', views.graph_view, name='graph'),
    path('graph/data/', views.graph_data, name='graph_data'),

    path('literatures/', views.literature_list, name='literature_list'),
    path('literatures/new/', views.literature_create, name='literature_create'),
    path('literatures/<int:pk>/', views.literature_detail, name='literature_detail'),
    path('literatures/<int:pk>/delete/', views.literature_delete, name='literature_delete'),

    path('disputes/', views.dispute_list, name='dispute_list'),
    path('disputes/new/', views.dispute_create, name='dispute_create'),
    path('disputes/<int:pk>/', views.dispute_detail, name='dispute_detail'),
    path('disputes/<int:pk>/resolve/', views.dispute_resolve, name='dispute_resolve'),
    path('disputes/<int:pk>/reject/', views.dispute_reject, name='dispute_reject'),
    path('disputes/<int:pk>/reopen/', views.dispute_reopen, name='dispute_reopen'),
    path('disputes/<int:pk>/delete/', views.dispute_delete, name='dispute_delete'),

    path('collations/', views.collation_list, name='collation_list'),
    path('collations/new/', views.collation_create, name='collation_create'),
    path('collations/<int:pk>/delete/', views.collation_delete, name='collation_delete'),

    path('deletion-requests/', views.deletion_request_list, name='deletion_request_list'),
    path('deletion-requests/new/<int:pk>/', views.deletion_request_create, name='deletion_request_create'),
    path('deletion-requests/<int:pk>/', views.deletion_request_detail, name='deletion_request_detail'),
    path('deletion-requests/<int:pk>/review/', views.deletion_request_review, name='deletion_request_review'),
    path('deletion-requests/<int:pk>/execute/', views.deletion_request_execute, name='deletion_request_execute'),
    path('deletion-requests/<int:pk>/cancel/', views.deletion_request_cancel, name='deletion_request_cancel'),

    path('annotations/<str:target_type>/<int:target_id>/create/', views.annotation_create, name='annotation_create'),
    path('annotations/<int:pk>/resolve/', views.annotation_resolve, name='annotation_resolve'),

    path('operation-logs/', views.operation_log_list, name='operation_log_list'),

    path('migrations/', views.migration_list, name='migration_list'),
    path('migrations/new/', views.migration_create, name='migration_create'),
    path('migrations/<int:pk>/', views.migration_detail, name='migration_detail'),
    path('migrations/<int:pk>/edit/', views.migration_edit, name='migration_edit'),
    path('migrations/<int:pk>/delete/', views.migration_delete, name='migration_delete'),
    path('migrations/<int:pk>/submit/', views.migration_submit, name='migration_submit'),
    path('migrations/<int:pk>/versions/', views.migration_version_history, name='migration_version_history'),
    path('migrations/<int:pk>/map-data/', views.migration_map_data, name='migration_map_data'),

    path('migration-reviews/', views.migration_review_list, name='migration_review_list'),
    path('migration-reviews/<int:pk>/', views.migration_review_detail, name='migration_review_detail'),

    path('migrations/<int:migration_pk>/stages/new/', views.migration_stage_create, name='migration_stage_create'),
    path('migration-stages/<int:pk>/edit/', views.migration_stage_edit, name='migration_stage_edit'),
    path('migration-stages/<int:pk>/delete/', views.migration_stage_delete, name='migration_stage_delete'),

    path('migrations/<int:migration_pk>/evidences/new/', views.migration_evidence_create, name='migration_evidence_create'),
    path('migration-evidences/<int:pk>/delete/', views.migration_evidence_delete, name='migration_evidence_delete'),

    path('migrations/<int:migration_pk>/disputes/new/', views.migration_dispute_create, name='migration_dispute_create'),
    path('migration-disputes/<int:pk>/', views.migration_dispute_detail, name='migration_dispute_detail'),
    path('migration-disputes/<int:pk>/resolve/', views.migration_dispute_resolve, name='migration_dispute_resolve'),
    path('migration-disputes/<int:pk>/reopen/', views.migration_dispute_reopen, name='migration_dispute_reopen'),
]
