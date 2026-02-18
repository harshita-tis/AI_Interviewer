from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("home/partials/<str:name>.html", views.partial_template, name="partial_template"),
    path('home/', views.index, name='index'),
    path('', views.login, name="login"),
    path('signup/', views.signup, name="signup"),
    path('logout/', views.logout_view, name="logout"),
    path("start-interview/", views.start_interview),
    path("next-question/", views.next_question),
    path("submit-answer/", views.submit_answer),
    path("generate-scorecard/", views.generate_scorecard),
    path("setup/", views.setup_screen, name="setup"),
    path("interview/", views.interview_screen, name="interview"),
    path("scorecard/", views.scorecard_screen, name="scorecard"),
    
]
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)