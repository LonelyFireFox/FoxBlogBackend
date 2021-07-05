from django.urls import path

from . import views

app_name = "blog"
urlpatterns = [
    path("", views.IndexView.as_view(), name="index"),
    path("posts/<int:pk>/", views.PostDetailView.as_view(), name="detail"),
    path(
        "archives/<int:year>/<int:month>/", views.ArchiveView.as_view(), name="archive"
    ),
    path("categories/<int:pk>/", views.CategoryView.as_view(), name="category"),
    path("tags/<int:pk>/", views.TagView.as_view(), name="tag"),
    # path('api/index/', views.index)
    # path('api/index/', views.IndexPostListAPIView.as_view())
    # path("api/index/", index), 使用视图集，直接在blogproject的urls文件中直接注册即可
]
