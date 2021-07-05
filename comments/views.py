from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from rest_framework import mixins, viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from blog.models import Post

from .forms import CommentForm
from .models import Comment
from .serializers import CommentSerializer


@require_POST
def comment(request, post_pk):
    # 先获取被评论的文章，因为后面需要把评论和被评论的文章关联起来。
    # 这里我们使用了 Django 提供的一个快捷函数 get_object_or_404，
    # 这个函数的作用是当获取的文章（Post）存在时，则获取；否则返回 404 页面给用户。
    print(111)
    post = get_object_or_404(Post, pk=post_pk)

    # django 将用户提交的数据封装在 request.POST 中，这是一个类字典对象。
    # 我们利用这些数据构造了 CommentForm 的实例，这样就生成了一个绑定了用户提交数据的表单。
    form = CommentForm(request.POST)

    # 当调用 form.is_valid() 方法时，Django 自动帮我们检查表单的数据是否符合格式要求。
    if form.is_valid():
        # 检查到数据是合法的，调用表单的 save 方法保存数据到数据库，
        # commit=False 的作用是仅仅利用表单的数据生成 Comment 模型类的实例，但还不保存评论数据到数据库。
        comment = form.save(commit=False)

        # 将评论和被评论的文章关联起来。
        comment.post = post

        # 最终将评论数据保存进数据库，调用模型实例的 save 方法
        comment.save()

        messages.add_message(request, messages.SUCCESS, "评论发表成功！", extra_tags="success")

        # 重定向到 post 的详情页，实际上当 redirect 函数接收一个模型的实例时，它会调用这个模型实例的 get_absolute_url 方法，
        # 然后重定向到 get_absolute_url 方法返回的 URL。
        return redirect(post)

    # 检查到数据不合法，我们渲染一个预览页面，用于展示表单的错误。
    # 注意这里被评论的文章 post 也传给了模板，因为我们需要根据 post 来生成表单的提交地址。
    context = {
        "post": post,
        "form": form,
    }
    messages.add_message(
        request, messages.ERROR, "评论发表失败！请修改表单中的错误后重新提交。", extra_tags="danger"
    )

    return render(request, "comments/preview.html", context=context)


class CommentViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    博客评论视图集

    create:
    创建博客评论
    """

    serializer_class = CommentSerializer

    def get_queryset(self):  # pragma: no cover
        return Comment.objects.all()

    # def create(self, request, *args, **kwargs):
        # 重写create方法，增加文章评论数+1的操作
        # serializer = self.get_serializer(data=request)
        # print(serializer)
        # post = get_object_or_404(Post, pk=data['post'])
        # post.increase_comment_count()
        # print(post)

    def create(self, request, *args, **kwargs):
        # print('request.data==>>', request.data)
        post = get_object_or_404(Post, pk=request.data['post'])
        post.increase_comment_count()
        # print('post',post)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(methods=['put'], detail=True)
    def like(self, request, pk):
        comment = get_object_or_404(Comment, pk=pk)
        comment.increase_like_count()
        serializer = self.get_serializer(comment)
        return Response(data=serializer.data, status=status.HTTP_200_OK)

    @action(methods=['put'], detail=True)
    def dislike(self, request, pk):
        comment = get_object_or_404(Comment, pk=pk)
        comment.increase_dislike_count()
        serializer = self.get_serializer(comment)
        return Response(data=serializer.data, status=status.HTTP_200_OK)
