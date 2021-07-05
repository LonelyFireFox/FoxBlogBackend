from rest_framework import serializers

from .models import Comment


class CommentSerializer(serializers.ModelSerializer):

    created_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", required=False, read_only=True)

    class Meta:
        model = Comment
        fields = [
            "id",
            "name",
            "email",
            "url",
            "content",
            "created_time",
            "post",
            "parent",
            "like_count",
            "dislike_count"
        ]
        extra_kwargs = {"post": {"write_only": True}}
