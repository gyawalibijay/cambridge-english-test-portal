"""One owner for Reading part navigation, answer saving, progress and deadlines."""
import math
from decimal import Decimal
from functools import wraps

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F, Sum
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from attempts.marking import mark_objective_question, normalize
from attempts.models import AttemptQuestion, StudentResponse, TestAttempt
from commerce.services import has_program_access
from question_bank.models import Question
from .models import MockTest, TestPart
from .reading_reference_data import PART_SECONDS, SLUG


def reading_access(view):
    @wraps(view)
    @login_required
    @never_cache
    def wrapped(request, *args, **kwargs):
        test = get_object_or_404(MockTest.objects.select_related("program"), slug=SLUG, is_published=True)
        if not has_program_access(request.user, test.program):
            return redirect("/store/?locked=" + test.program.code)
        request.reading_test = test
        return view(request, *args, **kwargs)
    return wrapped


def _part(test, number):
    return get_object_or_404(TestPart, section__mock_test=test, section__skill="reading", order=number)


def _assignments(part):
    return part.question_assignments.filter(question__is_active=True).select_related("question").order_by("order")


def _ready(part):
    return part.is_active and _assignments(part).exists()


def _set_size(part):
    # V36: every supplied Reading Set has exactly four questions in each
    # of Parts 1–5 (20 answers per Set). Assignment order is stable.
    return 4


def _set_assignments(part, number):
    size = _set_size(part)
    return _assignments(part).filter(order__gt=(number - 1) * size, order__lte=number * size)


def _available_sets(part):
    size = _set_size(part)
    return {(order - 1) // size + 1 for order in _assignments(part).values_list("order", flat=True) if order > 0}


def _set_number(attempt):
    try:
        return max(1, int(attempt.metadata.get("practice_set", 1)))
    except (ValueError, TypeError):
        return 1


def _state(test, user, part_number):
    history = [a for a in TestAttempt.objects.filter(user=user, mock_test=test).order_by("-pk")
               if a.metadata.get("practice_part") == part_number]
    active = next((a for a in history if a.status == TestAttempt.Status.IN_PROGRESS), None)
    finished = [a for a in history if a.status == TestAttempt.Status.COMPLETED and a.metadata.get("reading_finished")]
    completed = {_set_number(a) for a in finished}
    pending = 1
    while pending in completed:
        pending += 1
    return {"resume": active, "completed": completed, "next_set": pending,
            "last": finished[0] if finished else None}


def _current(attempt):
    return attempt.attempt_questions.filter(response__isnull=True).select_related("question__stimulus", "part").order_by("order").first()


def _deadline(attempt):
    return float(attempt.metadata.get("reading_deadline", attempt.started_at.timestamp() + PART_SECONDS))


def _owned(request, attempt_id):
    # A no-op write acquires a row/write lock before reading: also safe on SQLite.
    query = TestAttempt.objects.filter(pk=attempt_id, user=request.user, mock_test=request.reading_test)
    if not query.update(status=F("status")):
        raise Http404
    return query.get()


def _finish(attempt, expired=False):
    if attempt.status != TestAttempt.Status.IN_PROGRESS:
        return
    if expired:
        for item in attempt.attempt_questions.filter(response__isnull=True):
            StudentResponse.objects.create(
                attempt_question=item, answer_data={"unanswered": True, "reason": "time_expired"},
                is_correct=False, auto_score=0, final_score=0,
                review_status=StudentResponse.ReviewStatus.AUTO_GRADED,
            )
    attempt.overall_score = StudentResponse.objects.filter(attempt_question__attempt=attempt).aggregate(total=Sum("final_score"))["total"] or Decimal("0")
    attempt.status = TestAttempt.Status.COMPLETED
    attempt.completed_at = timezone.now()
    attempt.metadata = {**attempt.metadata, "reading_finished": True, "reading_timed_out": expired}
    attempt.save(update_fields=["overall_score", "status", "completed_at", "metadata"])


def _after(attempt):
    # Never advance to another Reading part. Intro resolves the user's next
    # uncompleted set on the server, or shows the end of available material.
    return reverse("assessments:reading_intro", args=[int(attempt.metadata["practice_part"])])


@login_required
@never_cache
@require_GET
def parts(request):
    test = MockTest.objects.filter(slug=SLUG, is_published=True).first()
    available = list(TestPart.objects.filter(section__mock_test=test).order_by("order")) if test else []
    completed = set()
    for part in available:
        state = _state(test, request.user, part.order)
        available_sets = _available_sets(part)
        if available_sets and available_sets <= state["completed"] and not state["resume"]:
            completed.add(part.order)
    lookup = {part.order: part for part in available}
    rows = [{"number": n, "ready": bool(lookup.get(n) and _ready(lookup[n])), "completed": n in completed}
            for n in range(1, 6)]
    return render(request, "reading_reference/parts.html", {"parts": rows})


@reading_access
@require_GET
def intro(request, part_number):
    part = _part(request.reading_test, part_number)
    if not _ready(part):
        return redirect("assessments:reading_parts")
    state = _state(request.reading_test, request.user, part_number)
    resume = state["resume"]
    set_number = _set_number(resume) if resume else state["next_set"]
    count = _set_assignments(part, set_number).count()
    if resume and _deadline(resume) <= timezone.now().timestamp():
        # Expiry is committed on the runner; GET intro itself does not reset time.
        return redirect("assessments:reading_runner", attempt_id=resume.pk)
    if not resume and not count:
        last = state["last"]
        return render(request, "reading_reference/sets_complete.html", {
            "part": part, "last": last, "set_number": _set_number(last) if last else None,
        })
    if part_number == 1:
        bullets = [f"You will read {count} short texts.", "Read each text and choose the correct answer."]
    elif part_number in (2, 3):
        bullets = [f"You will read {count} short sentences. A word is missing in each sentence.",
                   "Choose the correct word to complete each sentence." if part_number == 2
                   else "Write the missing word to complete each sentence."]
    else:
        bullets = part.instructions.splitlines()
    return render(request, "reading_reference/intro.html", {
        "part": part, "bullets": bullets, "resume": resume, "set_number": set_number,
    })


@reading_access
@require_POST
@transaction.atomic
def start(request, part_number):
    # Serialise two simultaneous Start clicks for the same user on every DB backend.
    get_user_model().objects.filter(pk=request.user.pk).update(last_login=F("last_login"))
    part = _part(request.reading_test, part_number)
    if not _ready(part):
        return redirect("assessments:reading_parts")
    state = _state(request.reading_test, request.user, part_number)
    previous = state["resume"]
    restarting = request.POST.get("restart") == "1"
    set_number = state["next_set"]
    if previous:
        # A stale/double-clicked restart must not cancel the replacement attempt.
        if not restarting or request.POST.get("resume_attempt") != str(previous.pk):
            return redirect("assessments:reading_runner", attempt_id=previous.pk)
        set_number = _set_number(previous)
    assignments = list(_set_assignments(part, set_number))
    if not assignments and not previous:
        last = state["last"]
        # At the end of supplied content, repeat only the last completed set.
        # Neither GET nor POST accepts a student-selected set number.
        if restarting and last and request.POST.get("repeat_from") == str(last.pk):
            set_number = _set_number(last)
            assignments = list(_set_assignments(part, set_number))
    if not assignments:
        return redirect("assessments:reading_intro", part_number=part_number)
    # Validate before creating an attempt, so incomplete authoring cannot strand a student.
    for assignment in assignments:
        q = assignment.question
        if q.question_type == Question.Type.SINGLE_CHOICE:
            valid = q.options.count() >= 2 and q.options.filter(is_correct=True).count() == 1
        elif q.question_type in (Question.Type.SHORT_ANSWER, Question.Type.GAP_FILL):
            valid = q.acceptable_answers.exclude(answer_text="").exists()
        else:
            valid = False
        if not valid:
            return HttpResponseBadRequest("This Reading part needs a content review before it can start.")
    if previous:
        previous.status = TestAttempt.Status.CANCELLED
        previous.save(update_fields=["status"])
    attempt = TestAttempt.objects.create(user=request.user, mock_test=request.reading_test, metadata={
        "practice_skill": "reading", "practice_part": part_number, "practice_set": set_number,
        "practice_mode": "part_set", "reading_reference": 1,
        "reading_set_queue": 1,
        "reading_deadline": timezone.now().timestamp() + PART_SECONDS,
    })
    total = Decimal("0")
    for position, assignment in enumerate(assignments, 1):
        points = assignment.points_override if assignment.points_override is not None else assignment.question.default_points
        AttemptQuestion.objects.create(attempt=attempt, part=part, question=assignment.question, order=position, points=points)
        total += points
    attempt.max_score = total
    attempt.save(update_fields=["max_score"])
    return redirect("assessments:reading_runner", attempt_id=attempt.pk)


def _screen(request, attempt, item, error="", submitted="", status=200):
    count = attempt.attempt_questions.count()
    instruction = {
        1: "Read and choose the correct answer",
        2: "Read and choose the correct word",
        3: "Read the sentence and write the correct answer",
        4: "Read the message and complete the form",
        5: "Read the text and choose the correct answer",
    }.get(item.part.order, "Read and answer the question")
    remaining_ms = max(0, math.floor((_deadline(attempt) - timezone.now().timestamp()) * 1000))
    remaining = math.ceil(remaining_ms / 1000)
    return render(request, "reading_reference/runner.html", {
        "attempt": attempt, "item": item, "total": count, "position": item.order,
        "set_number": _set_number(attempt),
        "progress": round(item.order / count * 100), "instruction": instruction,
        "remaining_ms": remaining_ms, "remaining_label": f"{remaining // 60:02d}:{remaining % 60:02d}",
        "is_choice": item.question.question_type == Question.Type.SINGLE_CHOICE,
        "options": item.question.options.order_by("order"), "error": error, "submitted": submitted,
    }, status=status)


@reading_access
@require_GET
@transaction.atomic
def runner(request, attempt_id):
    attempt = _owned(request, attempt_id)
    if attempt.status != TestAttempt.Status.IN_PROGRESS:
        return redirect(_after(attempt))
    if timezone.now().timestamp() >= _deadline(attempt):
        _finish(attempt, expired=True)
        return redirect(_after(attempt))
    item = _current(attempt)
    if not item:
        _finish(attempt)
        return redirect(_after(attempt))
    return _screen(request, attempt, item)


@reading_access
@require_POST
@transaction.atomic
def answer(request, attempt_id, question_id=None):
    attempt = _owned(request, attempt_id)
    if attempt.status != TestAttempt.Status.IN_PROGRESS:
        return redirect(_after(attempt))
    if timezone.now().timestamp() >= _deadline(attempt):
        _finish(attempt, expired=True)
        return redirect(_after(attempt))
    item = _current(attempt)
    if item is None:
        _finish(attempt)
        return redirect(_after(attempt))
    # Replayed requests cannot overwrite an answer or submit the next item for the user.
    if str(question_id or request.POST.get("item", "")) != str(item.pk):
        return redirect("assessments:reading_runner", attempt_id=attempt.pk)
    text = normalize(request.POST.get("text", ""))
    if item.question.question_type == Question.Type.SINGLE_CHOICE:
        option = request.POST.get("option", "")
        if not option.isascii() or not option.isdecimal() or len(option) > 18 or not item.question.options.filter(pk=int(option)).exists():
            return _screen(request, attempt, item, "Choose one of the answers.", status=400)
    elif not text or len(text) > 120:
        return _screen(request, attempt, item, "Write the missing word.", text[:120], status=400)
    correct, data = mark_objective_question(item.question, request.POST)
    score = item.points if correct else Decimal("0")
    StudentResponse.objects.create(
        attempt_question=item, text_response=text if "text" in data else "", answer_data=data,
        is_correct=correct, auto_score=score, final_score=score,
        review_status=StudentResponse.ReviewStatus.AUTO_GRADED,
    )
    if _current(attempt) is None:
        _finish(attempt)
        return redirect(_after(attempt))
    return redirect("assessments:reading_runner", attempt_id=attempt.pk)


@reading_access
@require_POST
@transaction.atomic
def expire(request, attempt_id):
    attempt = _owned(request, attempt_id)
    if attempt.status == TestAttempt.Status.IN_PROGRESS:
        if timezone.now().timestamp() < _deadline(attempt):
            return redirect("assessments:reading_runner", attempt_id=attempt.pk)
        _finish(attempt, expired=True)
    return redirect(_after(attempt))


def _number(value):
    try:
        number = int(value)
    except (ValueError, TypeError):
        raise Http404
    if number not in range(1, 6):
        raise Http404
    return number


@login_required
@require_GET
def test_intro(request):
    return redirect("assessments:reading_intro", part_number=_number(request.GET.get("part", "1")))


@login_required
@require_POST
def test_start(request):
    return start(request, _number(request.POST.get("part", "1")))
