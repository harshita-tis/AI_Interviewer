from logging import RootLogger
from django.shortcuts import render, redirect
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.auth.models import User
from .models import *
from .gemini_utils import (
    generate_questions, evaluate_answer, calculate_scores, generate_scorecard_content
)
from django.contrib import messages
from django.http import JsonResponse, Http404
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.conf import settings
from datetime import datetime, timedelta
from django.shortcuts import get_object_or_404
import jwt
from django.utils import timezone

def generate_jwt(user):
    payload = {
        "user_id": user.id,
        "exp": datetime.utcnow() + timedelta(days=7),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


@login_required(login_url="login")
def setup_screen(request):
    return render(request, "setup_screen.html")

@login_required(login_url="login")
def interview_screen(request):
    return render(request, "interview_screen.html")

@login_required(login_url="login")
def scorecard_screen(request):
    return render(request, "scorecard.html")

PARTIAL_TEMPLATES = {
    "base": "partials/base.html",
    "setup": "partials/setup.html",
    "interview": "partials/interview.html",
    "scorecard": "partials/scorecard.html",
}


@login_required(login_url="login")
def partial_template(request, name: str):
    template = PARTIAL_TEMPLATES.get(name)
    if not template:
        raise Http404("Partial not found")
    return render(request, template)

@login_required(login_url="login")
def index(request):
    context = {
        "title": "AI Interviewer",
        "message": "Welcome to AI Interview Module"
    }
    return render(request, 'home/index.html', context)
# -----------------------------
# START INTERVIEW
# -----------------------------

def login(request):
    # If already authenticated, go directly to home
    if request.user.is_authenticated:
        return redirect("index")

    if request.method == "POST":
        print("inside post method")
        email = request.POST.get("email")
        print("email-:",email)
        password = request.POST.get("password")
        print("password-:",password)

        user = authenticate(request, username=email, password=password)
        # user = get_object_or_404(AppUser,username=email,password=password)
        print("user-:",user)

        if not user:
            messages.error(request, "Invalid email or password")
            return redirect("login")

        if not user.is_active:
            messages.error(request, "Account is disabled")
            return redirect("login")
        # Log the user in using Django's session framework
        auth_login(request, user)
        return redirect("index")

    return render(request, "auth/login.html")


def logout_view(request):
    """Log out current user and redirect to login page."""
    auth_logout(request)
    return redirect("login")

def signup(request):
    if request.method == "POST":
        full_name = request.POST.get("full_name")
        email = request.POST.get("email")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        if password != confirm_password:
            messages.error(request, "Passwords do not match")
            return redirect("signup")

        if AppUser.objects.filter(email=email).exists():
            messages.error(request, "Email already exists")
            return redirect("signup")

        # ✅ Create user
        user = AppUser.objects.create_user(
            username=email,
            email=email,
            password=password,
            full_name=full_name,
        )
        
        user.save()
        
        messages.success(request, " account created successfully")
        return redirect("login")
    return render(request, 'auth/signup.html')

@api_view(['POST'])
def start_interview(request):

    name = request.data.get("name")
    role = request.data.get("role")
    experience = request.data.get("experience")
    skills = request.data.get("skills", "")

    if not role:
        return Response({"error": "Role is required"}, status=400)

    if not experience:
        return Response({"error": "Experience level is required"}, status=400)

    user = request.user if request.user.is_authenticated else User.objects.first()

    # 🔥 Delete old interview if exists (important)
    # UserProfile.objects.filter(user=user).delete()

    profile = UserProfile.objects.create(
        name=name,
        user=user,
        role=role,
        experience_years=experience,
        skills=skills,
    )

    # 🔥 ONE AI CALL HERE
    questions = generate_questions(
        role=role,
        experience=experience,
        skills=skills,
        candidate_name=name
    )

    # Save all questions
    for q in questions:
        InterviewQuestion.objects.create(
            profile=profile,
            role=role,
            question_text=q,
            difficulty="medium",
            skill_tag="General"
        )

    # Return first question instantly
    first_question = InterviewQuestion.objects.filter(profile=profile).first()

    return Response({
        "session_id": profile.id,
        "question": first_question.question_text,
        "question_id": first_question.id,
        "is_completed": False
    })


@api_view(['POST'])
def next_question(request):
    print(request.user)

    if not request.user.is_authenticated:
        return Response({"error": "Unauthorized"}, status=401)
    
    profile_id = request.data.get("profile_id")

    profile = UserProfile.objects.get(id=profile_id)

    # Get answered question IDs
    answered_ids = InterviewAnswer.objects.filter(
        profile=profile
    ).values_list("question_id", flat=True)

    # Get next unanswered question
    next_q = InterviewQuestion.objects.filter(
        profile=profile
    ).exclude(
        id__in=answered_ids
    ).first()

    if not next_q:
        return Response({
            "is_completed": True
        })

    return Response({
        "question": next_q.question_text,
        "question_id": next_q.id,
        "is_completed": False
    })


# -----------------------------
# SUBMIT ANSWER
# -----------------------------
@api_view(['POST'])
def submit_answer(request):
    print("submit answer function")

    question_id = request.data.get("question_id")
    print("question_id-:",question_id)
    answer = request.data.get("answer")
    is_skipped = request.data.get("is_skipped", False)
    print("is skipped-:",is_skipped)
    response_time = request.data.get("response_time", 0)

    if not request.user.is_authenticated:
        return Response({"error": "User not authenticated"}, status=401)

    try:
        profile = UserProfile.objects.get(user=request.user)
        question = InterviewQuestion.objects.get(id=question_id)
    except:
        return Response({"error": "Invalid question or profile"}, status=400)

    evaluation = None
    score = 0

    if not is_skipped and answer:
        evaluation = evaluate_answer(
            question.question_text, answer,
            role=profile.role, skills=profile.skills
        )
        score = evaluation.get("technical_score", 0)

    InterviewAnswer.objects.create(
        profile=profile,
        question=question,
        answer_text=answer,
        is_skipped=is_skipped,
        response_time=response_time,
        score=score,
        ai_feedback=evaluation
    )

    return Response({
        "message": "Answer saved",
        "score": score,
        "evaluation": evaluation
    })



# -----------------------------
# GENERATE SCORECARD
# -----------------------------
@api_view(['POST'])
def generate_scorecard(request):
    """
    Generate and save the scorecard for a given UserProfile.
    Expects JSON: { "profile_id": <id> }
    """
    profile_id = request.data.get("profile_id")
    if not profile_id:
        return Response({"error": "profile_id required"}, status=400)

    profile = get_object_or_404(UserProfile, id=profile_id)

    # Get all answers for this profile
    answers = profile.answers.all()
    if not answers.exists():
        return Response({"error": "No interview answers found for this profile"}, status=400)

    # Prepare QnA data for calculate_scores
    qna_data = []
    for ans in answers:
        qna_data.append({
            "question": ans.question.question_text,
            "answer": ans.answer_text,
            "ai_response": ans.ai_feedback or {}
        })

    # Calculate scores
    scores = calculate_scores(qna_data)
    technical_avg = scores.get("technical_avg", 0)
    communication_avg = scores.get("communication_avg", 0)
    skill_breakdown = scores.get("skill_breakdown", {})
    communication_review = scores.get("communication_review", "")

    # Overall score
    overall_score = round((technical_avg * 0.6) + (communication_avg * 0.4), 2)

    # Total interview time (first to last answer)
    ordered = profile.answers.order_by("created_at")
    total_time = "N/A"
    if ordered.count() >= 1:
        first_ts = ordered.first().created_at
        last_ts = ordered.last().created_at
        delta = last_ts - first_ts
        mins = int(delta.total_seconds() // 60)
        secs = int(delta.total_seconds() % 60)
        total_time = f"{mins}m {secs}s" if mins else f"{secs}s"

    # QnA summary for AI
    qna_summary = "\n".join(
        f"Q: {q.get('question', '')[:200]} A: {q.get('answer', '')[:300]}"
        for q in qna_data
    )

    # AI-generated dynamic content
    dynamic = generate_scorecard_content(
        role=profile.role,
        skills=profile.skills or [],
        name=profile.name or "Candidate",
        technical_avg=technical_avg,
        communication_avg=communication_avg,
        skill_breakdown=skill_breakdown,
        qna_summary=qna_summary,
    )
    communication_review = dynamic.get("communication_review", communication_review)
    recommendation = dynamic.get("recommendation", "No recommendation available.")
    skill_wise_reviews = dynamic.get("skill_wise_reviews", {})

    # Save or update Scorecard
    scorecard, created = Scorecard.objects.update_or_create(
        profile=profile,
        defaults={
            "technical_score": technical_avg,
            "communication_score": communication_avg,
            "overall_score": overall_score,
            "skill_breakdown": skill_breakdown,
            "recommendation": recommendation
        }
    )

    return Response({
        "profile_id": profile.id,
        "name": profile.name,
        "role": profile.role,
        "experience_years": profile.get_experience_years_display() if profile.experience_years else "N/A",
        "skills": profile.skills or [],
        "technical": technical_avg,
        "communication": communication_avg,
        "overall": overall_score,
        "skill_breakdown": skill_breakdown,
        "communication_review": communication_review,
        "recommendation": recommendation,
        "skill_wise_reviews": skill_wise_reviews,
        "total_time": total_time,
    })


