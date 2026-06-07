from django.urls import path
from . import views

app_name = 'places'

urlpatterns = [
    path('', views.index, name='index'),
    path('places/', views.place_list, name='place_list'),
    path('places/<int:pk>/', views.place_detail, name='place_detail'),
    path('relations/', views.relation_list, name='relation_list'),
    path('graph/', views.graph_view, name='graph'),
    path('graph/data/', views.graph_data, name='graph_data'),
    path('literatures/', views.literature_list, name='literature_list'),
    path('disputes/', views.dispute_list, name='dispute_list'),
    path('collations/', views.collation_list, name='collation_list'),
]
