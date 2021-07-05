from django.db.models import Count
from django.forms import model_to_dict
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.generic import DetailView, ListView
from django_filters.rest_framework import DjangoFilterBackend
from drf_haystack.viewsets import HaystackViewSet
from drf_yasg import openapi
from drf_yasg.inspectors import FilterInspector
from drf_yasg.utils import swagger_auto_schema
from pure_pagination.mixins import PaginationMixin
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.generics import ListAPIView
from rest_framework.pagination import LimitOffsetPagination, PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.serializers import DateField
from rest_framework.throttling import AnonRateThrottle
from rest_framework_extensions.cache.decorators import cache_response
from rest_framework_extensions.key_constructor.bits import ListSqlQueryKeyBit, PaginationKeyBit, RetrieveSqlQueryKeyBit
from rest_framework_extensions.key_constructor.constructors import DefaultKeyConstructor

from comments.serializers import CommentSerializer

from .filters import PostFilter
from .models import Category, Post, Tag, About, TreeHole
from .serializers import (
    CategorySerializer, PostHaystackSerializer, PostListSerializer, PostRetrieveSerializer, TagSerializer,
    AboutRetrieveSerializer, CategoryWithCountSerializer, TagsWithCountSerializer, TreeHoleSerializer)
from .utils import UpdatedAtKeyBit


class IndexView(PaginationMixin, ListView):
    model = Post
    template_name = "blog/index.html"
    context_object_name = "post_list"
    paginate_by = 10


class CategoryView(IndexView):
    def get_queryset(self):
        cate = get_object_or_404(Category, pk=self.kwargs.get("pk"))
        return super().get_queryset().filter(category=cate)


class ArchiveView(IndexView):
    def get_queryset(self):
        year = self.kwargs.get("year")
        month = self.kwargs.get("month")
        return (
            super()
                .get_queryset()
                .filter(created_time__year=year, created_time__month=month)
        )


class TagView(IndexView):
    def get_queryset(self):
        t = get_object_or_404(Tag, pk=self.kwargs.get("pk"))
        return super().get_queryset().filter(tags=t)


# 记得在顶部导入 DetailView
class PostDetailView(DetailView):
    # 这些属性的含义和 ListView 是一样的
    model = Post
    template_name = "blog/detail.html"
    context_object_name = "post"

    def get(self, request, *args, **kwargs):
        # 覆写 get 方法的目的是因为每当文章被访问一次，就得将文章阅读量 +1
        # get 方法返回的是一个 HttpResponse 实例
        # 之所以需要先调用父类的 get 方法，是因为只有当 get 方法被调用后，
        # 才有 self.object 属性，其值为 Post 模型实例，即被访问的文章 post
        response = super().get(request, *args, **kwargs)

        # 将文章阅读量 +1
        # 注意 self.object 的值就是被访问的文章 post
        self.object.increase_views()

        # 视图必须返回一个 HttpResponse 对象
        return response


# ---------------------------------------------------------------------------
#   Django REST framework 接口
# ---------------------------------------------------------------------------


class PostUpdatedAtKeyBit(UpdatedAtKeyBit):
    key = "post_updated_at"


class CommentUpdatedAtKeyBit(UpdatedAtKeyBit):
    key = "comment_updated_at"


class PostListKeyConstructor(DefaultKeyConstructor):
    list_sql = ListSqlQueryKeyBit()
    pagination = PaginationKeyBit()
    updated_at = PostUpdatedAtKeyBit()


class PostObjectKeyConstructor(DefaultKeyConstructor):
    retrieve_sql = RetrieveSqlQueryKeyBit()
    updated_at = PostUpdatedAtKeyBit()


class AboutObjectKeyConstructor(DefaultKeyConstructor):
    retrieve_sql = RetrieveSqlQueryKeyBit()
    updated_at = PostUpdatedAtKeyBit()


class CommentListKeyConstructor(DefaultKeyConstructor):
    list_sql = ListSqlQueryKeyBit()
    pagination = PaginationKeyBit()
    updated_at = CommentUpdatedAtKeyBit()


class IndexPostListAPIView(ListAPIView):
    serializer_class = PostListSerializer
    # 序列化博客文章（Post）列表（通过 queryset 指定）
    queryset = Post.objects.all()
    pagination_class = PageNumberPagination
    # 允许任何人访问该资源（AllowAny 权限类不对任何访问做拦截，即允许任何人调用这个 API 以访问其资源）
    permission_classes = [AllowAny]


class PostViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """
    博客文章视图集

    list:
    返回博客文章列表

    retrieve:
    返回博客文章详情

    list_comments:
    返回博客文章下的评论列表

    list_comments_all:
    返回博客文章下的评论列表，树状数据结构

    list_archive_dates:
    返回博客文章归档日期列表

    like
    点赞文章，修改点赞数字段
    """

    serializer_class = PostListSerializer
    queryset = Post.objects.all()
    permission_classes = [AllowAny]
    serializer_class_table = {
        "list": PostListSerializer,
        "retrieve": PostRetrieveSerializer,
    }
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = PostFilter
    ordering_fields = ['comment_count', 'like_count', 'views']

    def get_serializer_class(self):
        return self.serializer_class_table.get(
            self.action, super().get_serializer_class()
        )

    @cache_response(timeout=5 * 60, key_func=PostListKeyConstructor())
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @cache_response(timeout=5 * 60, key_func=PostObjectKeyConstructor())
    def retrieve(self, request, *args, **kwargs):
        # 重写retrieve方法，增加阅读量+1的操作
        instance = self.get_object()
        instance.increase_views()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @swagger_auto_schema(responses={200: "归档日期列表，时间倒序排列。例如：['2020-08', '2020-06']。"})
    @action(
        methods=["GET"],
        detail=False,
        url_path="archive/dates",
        url_name="archive-date",
        # filter_backends=None,
        # pagination_class=None,
    )
    def list_archive_dates(self, request, *args, **kwargs):
        dates = Post.objects.dates("created_time", "month", order="DESC")
        date_field = DateField()
        data = [date_field.to_representation(date)[:7] for date in dates]
        # <Response status_code=200, "text/html; charset=utf-8">
        return Response(data=data, status=status.HTTP_200_OK)

    @cache_response(timeout=5 * 60, key_func=CommentListKeyConstructor())
    @action(
        methods=["GET"],
        detail=True,
        url_path="comments",
        url_name="comment",
        # filter_backends=None,  # 移除从 PostViewSet 自动继承的 filter_backends，这样 drf-yasg 就不会生成过滤参数
        suffix="List",  # 将这个 action 返回的结果标记为列表，否则 drf-yasg 会根据 detail=True 将结果误判为单个对象
        pagination_class=LimitOffsetPagination,
        serializer_class=CommentSerializer,
    )
    def list_comments(self, request, *args, **kwargs):
        # 根据 URL 传入的参数值（文章 id）获取到博客文章记录
        post = self.get_object()
        # 获取文章下关联的全部评论
        queryset = post.comment_set.all().order_by("-created_time")
        # 对评论列表进行分页，根据 URL 传入的参数获取指定页的评论
        page = self.paginate_queryset(queryset)
        # 序列化评论
        serializer = self.get_serializer(page, many=True)
        # 返回分页后的评论列表
        return self.get_paginated_response(serializer.data)

    # @cache_response(timeout=5 * 60, key_func=CommentListKeyConstructor())
    @action(
        methods=["GET"],
        detail=True,
        url_path="allcomments",
        url_name="allcomments",
        suffix="List",  # 将这个 action 返回的结果标记为列表，否则 drf-yasg 会根据 detail=True 将结果误判为单个对象
        serializer_class=CommentSerializer,
    )
    def list_comments_all(self, request, *args, **kwargs):
        # 根据 URL 传入的参数值（文章 id）获取到博客文章记录
        post = self.get_object()
        # 获取文章下关联的全部评论
        queryset = post.comment_set.all().order_by("-created_time")
        comments_list = list_to_tree(list(queryset.values()))
        return Response(data=comments_list, status=status.HTTP_200_OK)

    @action(methods=['put'], detail=True)
    def like(self, request, pk):
        post = get_object_or_404(Post, pk=pk)
        post.increase_like_count()
        serializer = self.get_serializer(post)
        return Response(data=serializer.data, status=status.HTTP_200_OK)

    @action(methods=['get'], detail=False, url_path="archives",
            url_name="archives", )
    def list_archive(self, request, *args, **kwargs):
        # 获取所有文章，找出最早的年份，构造年份数组，
        result = []

        # 1. 获取所有日期
        dates = Post.objects.dates("created_time", "month", order="DESC")
        date_field = DateField()
        date_list = [date_field.to_representation(date)[:7] for date in dates]
        # print(date_list)
        # 2. 查出所有文章
        post_list = Post.objects.all()
        # print(len(post_list))

        # 构造返回的数据结构
        # reuslt = [{2019:[{title1:'',created_time1:''},{title2:'',created_time2:''}]},{}...{}]
        for date in date_list:
            result.append({date: []})
        # 3. 遍历将所有文章对象分配到相对应的年份
        for post in post_list:
            time_str = post.created_time.strftime('%Y-%m')
            for i in range(len(date_list)):
                if date_list[i] == time_str:
                    result[i][date_list[i]].append({'id': post.id, 'title': post.title,
                                                    'created_time': post.created_time.strftime('%Y-%m-%d %H:%M:%S')})
                    # 这里直接装post对象会报没序列化，直接返回相关字段好了
        # 返回对象为list
        return Response(data=result, status=status.HTTP_200_OK)


index = PostViewSet.as_view({"get": "list"})


def list_to_tree(list):
    tree = []
    # 遍历第一次，把所有根节点筛选出来
    for item in list[:]:
        if not item["parent_id"]:
            tree.append(item)
            list.remove(item)
    #     print(tree)
    #     print(list)
    # 继续遍历剩下的数据，找出子节点,直至list为空
    while len(list) > 0:
        for item in list[:]:
            # dfs 递归遍历寻找所有节点和子节点
            parent_node = find_parent(tree, item)
            # 找到其父节点，插入到children中
            # print('***')
            # print(parent_node)
            # 可能存在找完一趟根节点后，遍历到一个比如三级回复，而二级回复此时还没找完，那就先跳过，因为有while循环，跳过的最后还会再找
            # 相当于把深层的子节点寻找其父节点的任务后置了
            if parent_node is None:
                continue
            if 'children' not in parent_node.keys():
                parent_node['children'] = []
            parent_node['children'].append(item)

            list.remove(item)
    #         print(len(list))
    return tree


def find_parent(tree, item):
    # print(tree)
    # print('-----')
    result = None
    for p_item in tree:
        # 递归结束标志，找到该点
        # print(type(p_item),p_item)
        if p_item.get('id') == item.get('parent_id'):
            result = p_item
        elif 'children' in p_item.keys():
            result = find_parent(p_item['children'], item)

        if result is not None:
            return result


def format_comments(comment_list):
    """
    把相关评论的列表集合转换成如下的格式
    [
        {
            'id':comment_id,
            'content':'具体评论内容',
            'user':'评论人',
            'parent_id':id/None,
            'children':[
                {},
                {},
                ...
            ]
        },
        ...
    }
    """
    formated_list = []
    tmp_list = []

    for comment in comment_list:
        cid = comment['id']
        pid = comment.get('parent_id')
        dic = {'id': cid, 'name': comment['name'], 'content': comment['content'], 'parent_id': pid,
               'post_id': comment['post_id'],
               'children': []}
        # tmp_list.append(dic)
        if not pid:
            formated_list.append(dic)
        else:
            for item in tmp_list:
                if item['id'] == pid:
                    item['children'].append(dic)
                    break
    return formated_list


class CategoryViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    博客文章分类视图集

    list:
    返回博客文章分类列表
    """

    serializer_class = CategorySerializer
    # 关闭分页
    pagination_class = None

    def get_queryset(self):
        return Category.objects.all().order_by("name")

    @action(methods=["GET"], detail=False, url_path='getCategoryAndCount', url_name='getCategoryAndCount',
            serializer_class=CategoryWithCountSerializer
            )
    def get_category_and_count(self, request, *args, **kwargs):
        category_list = Category.objects.annotate(num_posts=Count('post')).filter(num_posts__gt=0)
        serializer = self.get_serializer(instance=category_list, many=True)
        return Response(data=serializer.data, status=status.HTTP_200_OK)


class TagViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    博客文章标签视图集

    list:
    返回博客文章标签列表
    """

    serializer_class = TagSerializer
    # 关闭分页
    pagination_class = None

    def get_queryset(self):
        return Tag.objects.all().order_by("name")

    @action(methods=["GET"], detail=False, url_path='getTagsAndCount', url_name='getTagsAndCount',
            serializer_class=TagsWithCountSerializer
            )
    def get_tags_and_count(self, request, *args, **kwargs):
        tags_list = Tag.objects.annotate(num_posts=Count('post')).filter(num_posts__gt=0)
        serializer = self.get_serializer(instance=tags_list, many=True)
        return Response(data=serializer.data, status=status.HTTP_200_OK)


class PostSearchAnonRateThrottle(AnonRateThrottle):
    THROTTLE_RATES = {"anon": "5/min"}


class PostSearchFilterInspector(FilterInspector):
    def get_filter_parameters(self, filter_backend):
        return [
            openapi.Parameter(
                name="text",
                in_=openapi.IN_QUERY,
                required=True,
                description="搜索关键词",
                type=openapi.TYPE_STRING,
            )
        ]


@method_decorator(
    name="retrieve",
    decorator=swagger_auto_schema(
        auto_schema=None,
    ),
)
# @method_decorator(
#     name="list",
#     decorator=swagger_auto_schema(
#         operation_description="返回关键词搜索结果",
#         filter_inspectors=[PostSearchFilterInspector],
#     ),
# )
class PostSearchView(HaystackViewSet):
    """
    搜索视图集

    list:
    返回搜索结果列表
    """

    index_models = [Post]
    serializer_class = PostHaystackSerializer
    throttle_classes = [PostSearchAnonRateThrottle]


class ApiVersionTestViewSet(viewsets.ViewSet):  # pragma: no cover
    swagger_schema = None

    @action(
        methods=["GET"],
        detail=False,
        url_path="test",
        url_name="test",
    )
    def test(self, request, *args, **kwargs):
        if request.version == "v1":
            return Response(
                data={
                    "version": request.version,
                    "warning": "该接口的 v1 版本已废弃，请尽快迁移至 v2 版本",
                }
            )
        return Response(data={"version": request.version})


class AboutViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    关于我视图集

    list:
    返回关于我列表

    """
    serializer_class = AboutRetrieveSerializer
    # 关闭分页
    pagination_class = None
    queryset = About.objects.all()

    @action(
        methods=["GET"],
        detail=False,
    )
    def about_info(self, request, *args, **kwargs):
        data = About.objects.latest("created_time")
        serializer = self.get_serializer(instance=data)
        return Response(data=serializer.data, status=status.HTTP_200_OK)


class TreeHoleViewSet(
    mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    """
    树洞视图集

    list:
    返回树洞列表

    list_treeholes_all
    返回所有树洞数据，树状数据结构

    """
    queryset = TreeHole.objects.all()
    serializer_class = TreeHoleSerializer

    # permission_classes = [] # todo 控制admin用？

    @action(
        methods=["GET"],
        detail=False,
        url_path="alltreeholes",
        url_name="alltreeholes",
        suffix="List",  # 将这个 action 返回的结果标记为列表，否则 drf-yasg 会根据 detail=True 将结果误判为单个对象
        serializer_class=TreeHoleSerializer,
    )
    def list_treeholes_all(self, request, *args, **kwargs):
        result = []
        treeholes_list = TreeHole.objects.all()
        treeholes_formated_list = list_to_tree(list(treeholes_list.values()))
        print(treeholes_formated_list)
        # 再根据日期分类
        # 1. 获取所有日期
        dates = TreeHole.objects.dates("created_time", "month", order="DESC")
        date_field = DateField()
        date_list = [date_field.to_representation(date)[:7] for date in dates]
        for date in date_list:
            result.append({date: []})
        print(result)

        for obj in treeholes_formated_list:
            print(obj)
            time_str = obj['created_time'].strftime('%Y-%m')
            for i in range(len(date_list)):
                if date_list[i] == time_str:
                    result[i][date_list[i]].append({'id': obj['id'], 'content': obj['content'], 'parent': obj['parent_id'],
                                                    'created_time': obj['created_time'].strftime('%Y-%m-%d %H:%M:%S'),
                                                    'children':obj.get('children')
                                                    })

        return Response(data=result, status=status.HTTP_200_OK)
