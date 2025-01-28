from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Course, Lesson, Subscription
from .paginators import MaterialsPaginator
from .permissions import IsModerator, IsOwner, ReadOnlyForAll
from .serializers import CourseSerializer, LessonSerializer
from .tasks import send_update_notification


class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    pagination_class = MaterialsPaginator

    def get_permissions(self):
        if self.action in ["create"]:
            permission_classes = [permissions.IsAuthenticated & ~IsModerator]
        elif self.action in ["update", "partial_update", "destroy"]:
            permission_classes = [IsOwner | IsModerator]
        else:
            permission_classes = [ReadOnlyForAll | IsOwner | IsModerator]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @swagger_auto_schema(
        operation_description="Получить список всех курсов",
        responses={200: CourseSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Создать новый курс",
        request_body=CourseSerializer,
        responses={201: CourseSerializer()},
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Получить детали курса",
        responses={200: CourseSerializer()},
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Обновить курс",
        request_body=CourseSerializer,
        responses={200: CourseSerializer()},
    )
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        four_hours_ago = timezone.now() - timezone.timedelta(hours=4)

        response = super().update(request, *args, **kwargs)

        if instance.last_updated <= four_hours_ago:
            subscribers = instance.subscribers.all()
            for subscriber in subscribers:
                send_update_notification.delay(instance.id, subscriber.email)

        return response

    @swagger_auto_schema(
        operation_description="Частично обновить курс",
        request_body=CourseSerializer,
        responses={200: CourseSerializer()},
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Удалить курс", responses={204: "Курс успешно удален"}
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


class LessonViewSet(viewsets.ModelViewSet):
    queryset = Lesson.objects.all()
    serializer_class = LessonSerializer
    pagination_class = MaterialsPaginator

    def get_permissions(self):
        if self.action in ["create"]:
            permission_classes = [permissions.IsAuthenticated & ~IsModerator]
        elif self.action in ["update", "partial_update", "destroy"]:
            permission_classes = [IsOwner | IsModerator]
        else:
            permission_classes = [ReadOnlyForAll | IsOwner | IsModerator]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @swagger_auto_schema(
        operation_description="Получить список всех уроков",
        responses={200: LessonSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Создать новый урок",
        request_body=LessonSerializer,
        responses={201: LessonSerializer()},
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Получить детали урока",
        responses={200: LessonSerializer()},
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Обновить урок",
        request_body=LessonSerializer,
        responses={200: LessonSerializer()},
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Частично обновить урок",
        request_body=LessonSerializer,
        responses={200: LessonSerializer()},
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Удалить урок", responses={204: "Урок успешно удален"}
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


class SubscriptionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Подписаться или отписаться от курса",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "course_id": openapi.Schema(
                    type=openapi.TYPE_INTEGER, description="ID курса"
                )
            },
            required=["course_id"],
        ),
        responses={
            200: openapi.Response(
                "Успешная операция",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "message": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            description="Сообщение о результате",
                        )
                    },
                ),
            ),
            404: "Курс не найден",
        },
    )
    def post(self, request, *args, **kwargs):
        user = request.user
        course_id = request.data.get("course_id")
        course = get_object_or_404(Course, id=course_id)

        subscription, created = Subscription.objects.get_or_create(
            user=user, course=course
        )

        if created:
            message = "Подписка добавлена"
        else:
            subscription.delete()
            message = "Подписка удалена"

        return Response({"message": message}, status=status.HTTP_200_OK)
