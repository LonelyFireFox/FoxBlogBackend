from datetime import datetime

from django.core.cache import cache
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.utils import timezone


class Comment(models.Model):
    name = models.CharField("名字", max_length=50)
    email = models.EmailField("邮箱")
    url = models.URLField("网址", blank=True)
    content = models.TextField("内容")
    created_time = models.DateTimeField("创建时间", default=timezone.now)
    post = models.ForeignKey("blog.Post", verbose_name="文章", on_delete=models.CASCADE)
    like_count = models.IntegerField(default=0)
    dislike_count = models.IntegerField(default=0)

    """多级评论需要 自关联"""
    parent = models.ForeignKey("Comment", null=True, blank=True, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "评论"
        verbose_name_plural = verbose_name
        ordering = ["-created_time"]

    def __str__(self):
        return "{}: {}".format(self.name, self.content[:20])

    def increase_like_count(self):
        self.like_count += 1
        self.save(update_fields=["like_count"])

    def increase_dislike_count(self):
        self.dislike_count += 1
        self.save(update_fields=["dislike_count"])


def change_comment_updated_at(sender=None, instance=None, *args, **kwargs):
    cache.set("comment_updated_at", datetime.utcnow())


post_save.connect(receiver=change_comment_updated_at, sender=Comment)
post_delete.connect(receiver=change_comment_updated_at, sender=Comment)
