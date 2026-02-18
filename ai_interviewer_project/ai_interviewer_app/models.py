from django.db import models
from django.contrib.auth.models import AbstractUser



class AppUser(AbstractUser):

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=200,null=True)
    created_at = models.DateTimeField(auto_now_add=True,blank=True,null=True)




    def __str__(self):
        return self.email

class UserProfile(models.Model):

    EXPERIENCE_CHOICES = [
        ("0-2", "0-2 Years"),
        ("2-5", "2-5 Years"),
        ("5-8", "5-8 Years"),
        ("8+", "8+ Years"),
    ]

    user = models.ForeignKey(
        AppUser,
        on_delete=models.CASCADE,
        related_name="interview_profiles"
    )
    
    name = models.CharField(max_length=200,null=True)

    role = models.CharField(max_length=255)

    experience_years = models.CharField(
        max_length=10,
        choices=EXPERIENCE_CHOICES
    )

    skills = models.JSONField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.role}"
    
    
class InterviewQuestion(models.Model):

    DIFFICULTY_CHOICES = [
        ("easy", "Easy"),
        ("medium", "Medium"),
        ("hard", "Hard"),
    ]
    profile = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="questions"
    )
    role = models.CharField(max_length=255)
    question_text = models.TextField()

    difficulty = models.CharField(
        max_length=10,
        choices=DIFFICULTY_CHOICES
    )

    skill_tag = models.CharField(max_length=255)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.question_text[:50]
    
class InterviewAnswer(models.Model):

    profile = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="answers"
    )

    question = models.ForeignKey(
        InterviewQuestion,
        on_delete=models.CASCADE,
        related_name="answers"
    )

    answer_text = models.TextField(blank=True, null=True)

    is_skipped = models.BooleanField(default=False)

    response_time = models.IntegerField(null=True, blank=True)  # seconds

    score = models.FloatField(null=True, blank=True)

    ai_feedback = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.profile.user.username} - Q{self.question.id}"


class Scorecard(models.Model):
    profile = models.OneToOneField(
        "UserProfile", on_delete=models.CASCADE, related_name="scorecard"
    )
    technical_score = models.FloatField()
    communication_score = models.FloatField()
    overall_score = models.FloatField()
    skill_breakdown = models.JSONField(default=dict)  # per-skill scores & reviews
    recommendation = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Scorecard for {self.profile.name}"