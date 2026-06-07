from django.urls import path
from . import views

app_name = 'places'

urlpatterns = [
    path('', views.index, name='index'),
    path('places/', views.place_list, name='place_list'),
    path('places/new/', views.place_create, name='place_create'),
    path('places/<int:pk>/', views.place_detail, name='place_detail'),
    path('places/<int:pk>/delete/', views.place_delete, name='place_delete'),
    path('relations/', views.relation_list, name='relation_list'),
    path('relations/new/', views.relation_create, name='relation_create'),
    path('relations/<int:pk>/delete/', views.relation_delete, name='relation_delete'),
    path('graph/', views.graph_view, name='graph'),
    path('graph/data/', views.graph_data, name='graph_data'),
    path('literatures/', views.literature_list, name='literature_list'),
    path('literatures/new/', views.literature_create, name='literature_create'),
    path('literatures/<int:pk>/delete/', views.literature_delete, name='literature_delete'),
    path('disputes/', views.dispute_list, name='dispute_list'),
    path('disputes/new/', views.dispute_create, name='dispute_create'),
    path('disputes/<int:pk>/delete/', views.dispute_delete, name='dispute_delete'),
    path('collations/', views.collation_list, name='collation_list'),
    path('collations/new/', views.collation_create, name='collation_create'),
    path('collations/<int:pk>/delete/', views.collation_delete, name='collation_delete'),
]
