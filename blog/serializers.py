from django.contrib.auth.models import User
from drf_haystack.serializers import HaystackSerializerMixin
from rest_framework import serializers
from rest_framework.fields import CharField

from .models import Category, Post, Tag, About, TreeHole
from .utils import Highlighter


class CategorySerializer(serializers.ModelSerializer):

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
        ]


class CategoryWithCountSerializer(serializers.ModelSerializer):
    # 当需要额外的属性，比如聚合函数所赋予的新属性时，序列化类也要声明相应的属性，否则无法序列化
    num_posts = serializers.IntegerField()

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "num_posts"
        ]



class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
        ]


class TagSerializer(serializers.ModelSerializer):

    class Meta:
        model = Tag
        fields = [
            "id",
            "name",
        ]

class TagsWithCountSerializer(serializers.ModelSerializer):
    num_posts = serializers.IntegerField()

    class Meta:
        model = Tag
        fields = [
            "id",
            "name",
            "num_posts"
        ]


class PostListSerializer(serializers.ModelSerializer):
    category = CategorySerializer()
    author = UserSerializer()
    created_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", required=False, read_only=True)
    tags = TagSerializer(many=True)

    class Meta:
        model = Post
        # fields = "__all__"  # todo 显示所有的字段
        fields = [
            "id",
            "title",
            "created_time",
            "excerpt",
            "category",
            "author",
            "views",
            "like_count",
            "comment_count",
            "tags"
        ]


class PostRetrieveSerializer(serializers.ModelSerializer):
    category = CategorySerializer()
    author = UserSerializer()
    tags = TagSerializer(many=True)
    toc = serializers.CharField(label="文章目录", help_text="HTML 格式，每个目录条目均由 li 标签包裹。")
    body_html = serializers.CharField(
        label="文章内容", help_text="HTML 格式，从 `body` 字段解析而来。"
    )
    created_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", required=False, read_only=True)

    class Meta:
        model = Post
        fields = [
            "id",
            "title",
            "body",
            "created_time",
            "modified_time",
            "excerpt",
            "views",
            "category",
            "author",
            "tags",
            "toc",
            "body_html",
            "like_count",
            "comment_count"
        ]


class HighlightedCharField(CharField):
    def to_representation(self, value):
        value = super().to_representation(value)
        request = self.context["request"]
        query = request.query_params["text"]
        highlighter = Highlighter(query)
        return highlighter.highlight(value)


class PostHaystackSerializer(HaystackSerializerMixin, PostListSerializer):
    title = HighlightedCharField(
        label="标题", help_text="标题中包含的关键词已由 HTML 标签包裹，并添加了 class，前端可设置相应的样式来高亮关键。"
    )
    summary = HighlightedCharField(
        source="body",
        label="摘要",
        help_text="摘要中包含的关键词已由 HTML 标签包裹，并添加了 class，前端可设置相应的样式来高亮关键。",
    )

    class Meta(PostListSerializer.Meta):
        search_fields = ["text"]
        fields = [
            "id",
            "title",
            "summary",
            "created_time",
            "excerpt",
            "category",
            "author",
            "views",
        ]


class AboutRetrieveSerializer(serializers.ModelSerializer):
    body_html = serializers.CharField(
        label="文章内容", help_text="HTML 格式，从 `body` 字段解析而来。"
    )
    created_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", required=False, read_only=True)

    class Meta:
        model = About
        fields = [
            "id",
            "body",
            "created_time",
            "modified_time",
            "body_html",
        ]


class TreeHoleSerializer(serializers.ModelSerializer):
    created_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", required=False, read_only=True)

    class Meta:
        model = TreeHole
        fields = [
            "id",
            "content",
            "created_time",
            "modified_time",
            "parent",
        ]