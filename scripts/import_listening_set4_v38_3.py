from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.db import transaction
from django.db.models import Max

Program = apps.get_model('assessments', 'Program')
MockTest = apps.get_model('assessments', 'MockTest')
TestSection = apps.get_model('assessments', 'TestSection')
TestPart = apps.get_model('assessments', 'TestPart')
Question = apps.get_model('question_bank', 'Question')
Stimulus = apps.get_model('question_bank', 'Stimulus')
QuestionOption = apps.get_model('question_bank', 'QuestionOption')
AcceptableAnswer = apps.get_model('question_bank', 'AcceptableAnswer')
OrderingItem = apps.get_model('question_bank', 'OrderingItem')
PartQuestion = apps.get_model('question_bank', 'PartQuestion')

PAYLOAD = Path(os.environ['B1_LISTENING_SET4_PAYLOAD']).resolve()
if not PAYLOAD.is_dir():
    raise RuntimeError(f'Payload directory does not exist: {PAYLOAD}')


def names(model):
    return {f.name for f in model._meta.get_fields()}


def set_if(model, data, name, value):
    if name in names(model):
        data[name] = value


def find_program():
    ranked = []
    for obj in Program.objects.all():
        text = ' '.join(str(getattr(obj, x, '') or '') for x in ('name','short_name','code')).lower()
        score = 0
        if 'cambridge' in text: score += 10
        if 'general english' in text: score += 8
        if 'upskill' in text: score += 4
        if 'ielts' in text or 'ukvi' in text: score -= 20
        if score > 0:
            ranked.append((score, obj.pk, obj))
    if not ranked:
        raise RuntimeError('Cambridge / General English Program was not found.')
    ranked.sort(key=lambda x: (-x[0], x[1]))
    return ranked[0][2]


def ensure_structure(program):
    mock = MockTest.objects.filter(program=program, slug='cambridge-listening-practice-1').first()
    if mock is None:
        data = dict(program=program, title='Cambridge Listening Practice', slug='cambridge-listening-practice-1')
        set_if(MockTest, data, 'description', 'Cambridge Listening practice sets.')
        set_if(MockTest, data, 'instructions', '')
        set_if(MockTest, data, 'delivery_mode', 'practice')
        set_if(MockTest, data, 'is_published', True)
        set_if(MockTest, data, 'duration_minutes', 25)
        mock = MockTest.objects.create(**data)
    else:
        changed = []
        if 'is_published' in names(MockTest) and not mock.is_published:
            mock.is_published = True; changed.append('is_published')
        if 'delivery_mode' in names(MockTest) and mock.delivery_mode != 'practice':
            mock.delivery_mode = 'practice'; changed.append('delivery_mode')
        if changed: mock.save(update_fields=changed)

    section = TestSection.objects.filter(mock_test=mock, skill='listening').order_by('order','pk').first()
    if section is None:
        last = TestSection.objects.filter(mock_test=mock).aggregate(v=Max('order'))['v'] or 0
        data = dict(mock_test=mock, title='Listening', skill='listening', order=last+1)
        set_if(TestSection, data, 'instructions', '')
        set_if(TestSection, data, 'duration_seconds', 25*60)
        set_if(TestSection, data, 'can_pause', False)
        set_if(TestSection, data, 'is_required', True)
        section = TestSection.objects.create(**data)

    parts = {}
    for p in range(1, 6):
        part = TestPart.objects.filter(section=section, order=p).first()
        if part is None:
            data = dict(section=section, title=f'Listening Part {p}', order=p)
            set_if(TestPart, data, 'instructions', '')
            set_if(TestPart, data, 'prompt_mode', 'audio')
            set_if(TestPart, data, 'question_visible', True)
            set_if(TestPart, data, 'preparation_seconds', 0)
            set_if(TestPart, data, 'is_active', True)
            part = TestPart.objects.create(**data)
        parts[p] = part
    return mock, section, parts


# Source-derived Set 4 data. Audio scripts are kept as admin transcript metadata only.
DATA = {1: {'instruction': 'You will hear four short recordings as part of one chat. Choose the correct reply for each one. At the end, answer a question '
                    'about the whole chat.',
     'questions': [{'q': 1,
                    'type': 'single_choice',
                    'audio': 1,
                    'show': False,
                    'prompt': '',
                    'transcript': 'Speaker 1: [friendly] Are you still helping at the community garden on Saturday?',
                    'options': ['Yes, from nine until lunchtime.', 'I planted those flowers last year.', "Saturday's weather was warm."],
                    'correct': 1},
                   {'q': 2,
                    'type': 'single_choice',
                    'audio': 2,
                    'show': False,
                    'prompt': '',
                    'transcript': 'Speaker 1: [hopefully] Could I come with you?',
                    'options': ['I came by bus.', 'You can take these home.', 'Of course. They still need more volunteers.'],
                    'correct': 3},
                   {'q': 3,
                    'type': 'single_choice',
                    'audio': 3,
                    'show': False,
                    'prompt': '',
                    'transcript': 'Speaker 1: [inquiring] Do I need to bring any tools?',
                    'options': ['The garden is behind the library.', 'No, the organisers provide everything.', 'I need to finish some work.'],
                    'correct': 2},
                   {'q': 4,
                    'type': 'single_choice',
                    'audio': 4,
                    'show': False,
                    'prompt': '',
                    'transcript': "Speaker 1: [pleased] That's useful. I'll wear my old boots.",
                    'options': ['Good idea. The ground may be wet.', 'The tools are kept in a shed.', 'I bought some new shoes yesterday.'],
                    'correct': 1},
                   {'q': 5,
                    'type': 'single_choice',
                    'audio': None,
                    'show': True,
                    'prompt': 'What are the colleagues planning to do?',
                    'transcript': '',
                    'options': ['Buy equipment for a library.', 'Visit a garden after work.', 'Volunteer together on Saturday morning.'],
                    'correct': 3}]},
 2: {'instruction': 'Listen to part of a workplace conversation. Put the five actions the woman completed in the order you hear them.',
     'transcript': 'Speaker 1: [conversationally] How are we doing with the office move?\n'
                   "Speaker 2: [confidently] We're on schedule. I measured the new storage area, so we know which shelves will fit.\n"
                   'Speaker 1: [inquiring] And the old paper files?\n'
                   'Speaker 2: [matter-of-factly] I labelled all the archive boxes by department. The moving company then offered us two dates, and '
                   'I booked their van for Friday.\n'
                   "Speaker 1: [checking] Does the building manager know when we're arriving?\n"
                   'Speaker 2: [assured] Yes. I told the landlord that the van needs access from eight in the morning. I also emailed the new floor '
                   'plan to everyone here.\n'
                   'Speaker 1: [satisfied] Great. Is anything left?\n'
                   "Speaker 2: [forward-looking] We'll unplug the computers on Thursday evening.",
     'questions': [{'q': 1,
                    'type': 'ordering',
                    'audio': 1,
                    'show': True,
                    'prompt': 'Put the five completed actions in the order you hear them.',
                    'source_items': {'A': 'Sent staff the layout of the new office.',
                                     'B': 'Checked the size of the storage space.',
                                     'C': 'Informed the landlord about the arrival time.',
                                     'D': 'Marked the archive boxes by department.',
                                     'E': 'Reserved a vehicle for moving day.'},
                    'correct_order': ['B', 'D', 'E', 'C', 'A']}]},
 3: {'instruction': 'You will hear four short recordings. Listen and write the correct information in each gap.',
     'questions': [{'q': 1,
                    'type': 'short_answer',
                    'audio': 1,
                    'show': True,
                    'prompt': 'Reservation number: __________',
                    'transcript': "Speaker 1: [politely] I'm checking whether the book I reserved is ready to collect.\n"
                                  "Speaker 2: [professionally] I can check. What's your reservation number?\n"
                                  'Speaker 1: [carefully, reading individual digits] Two, six, four, nine, zero, seven.\n'
                                  "Speaker 2: [helpfully] Thank you. It's waiting at the front desk.",
                    'answers': ['264907']},
                   {'q': 2,
                    'type': 'short_answer',
                    'audio': 2,
                    'show': True,
                    'prompt': 'Surname: __________',
                    'transcript': 'Speaker 1: [politely] Hello. I need a copy of my test result.\n'
                                  'Speaker 2: [professionally] Certainly. Could you give me your surname?\n'
                                  'Speaker 1: [clearly, then spelling] Gurung. G-U-R-U-N-G.\n'
                                  "Speaker 2: [neutral] Thank you. I'll find your record.",
                    'answers': ['Gurung']},
                   {'q': 3,
                    'type': 'short_answer',
                    'audio': 3,
                    'show': True,
                    'prompt': 'The chairs will now be delivered on __________.',
                    'transcript': 'Speaker 1: [apologetically] Your chairs were due on the twelfth of June, but our driver is unavailable that week. '
                                  'We can deliver them on the nineteenth of June.\n'
                                  'Speaker 2: [accepting] The nineteenth is fine. Please send me the new delivery note.',
                    'answers': ['19 June']},
                   {'q': 4,
                    'type': 'short_answer',
                    'audio': 4,
                    'show': True,
                    'prompt': '---',
                    'transcript': "Speaker 1: [calmly] I'd like to ask about the payment on my policy.\n"
                                  'Speaker 2: [professionally] Before we begin, please tell me your five-digit security PIN.\n'
                                  'Speaker 1: [carefully, reading individual digits] Three, one, five, eight, two.\n'
                                  'Speaker 2: [neutral] Thank you. I can see your policy now.\n'
                                  "The customer's PIN is __________.",
                    'answers': ['31582']}]},
 4: {'instruction': 'You will hear four short recordings. For each one, choose the correct answer.',
     'questions': [{'q': 1,
                    'type': 'single_choice',
                    'audio': 1,
                    'show': True,
                    'prompt': 'What will the woman do?',
                    'transcript': 'Speaker 1: [concerned] I need to send this invoice before noon, but my computer is installing an update.\n'
                                  'Speaker 2: [helpfully] Use the spare computer beside my desk. Your account should work on it.\n'
                                  "Speaker 1: [relieved] Good. I'll send the invoice from there.",
                    'options': ['Wait for her computer to finish updating.',
                                'Use another computer to send the invoice.',
                                'Ask the man to prepare a new invoice.'],
                    'correct': 2},
                   {'q': 2,
                    'type': 'single_choice',
                    'audio': 2,
                    'show': True,
                    'prompt': 'Where will the man meet the engineer?',
                    'transcript': 'Speaker 1: [inquiring] Should I meet the visiting engineer at main reception?\n'
                                  'Speaker 2: [correcting gently] Not today. Her taxi is dropping her at the south gate, beside the workshop.\n'
                                  "Speaker 1: [acknowledging] I'll wait for her there.",
                    'options': ['At the south gate.', 'In the main reception area.', 'Inside the workshop.'],
                    'correct': 1},
                   {'q': 3,
                    'type': 'single_choice',
                    'audio': 3,
                    'show': True,
                    'prompt': 'What problem does the woman have?',
                    'transcript': 'Speaker 1: [puzzled] The cycle-hire app says there are no bicycles nearby, but I can see a full rack in front of '
                                  'me.\n'
                                  "Speaker 2: [helpfully] Your phone's location setting is switched off. Turn it on, and the app will show this "
                                  'station.',
                    'options': ['The bicycle rack is empty.', 'She has downloaded the wrong app.', 'Her phone is not sharing its location.'],
                    'correct': 3},
                   {'q': 4,
                    'type': 'single_choice',
                    'audio': 4,
                    'show': True,
                    'prompt': 'What does the man want the woman to do?',
                    'transcript': 'Speaker 1: [politely] Could you cover the front desk while I have lunch? A courier is coming at one, so someone '
                                  'needs to stay here.\n'
                                  "Speaker 2: [agreeably] That's fine. I'll take my break when you come back.",
                    'options': ['Meet him for lunch.', 'Work at reception during his break.', 'Contact the courier before one.'],
                    'correct': 2}]},
 5: {'instruction': 'You will hear four longer recordings. For each one, choose the correct answer.',
     'questions': [{'q': 1,
                    'type': 'single_choice',
                    'audio': 1,
                    'show': True,
                    'prompt': 'How does the woman feel about the event?',
                    'transcript': 'Speaker 1: [warmly] Your talk at the industry event is tomorrow. Are you nervous about speaking to such a large '
                                  'audience?\n'
                                  "Speaker 2: [confidently, then slightly anxious] The presentation itself is fine. I've practised it several times, "
                                  "and I know the subject well. It's the questions afterwards that worry me. Someone may ask about figures I don't "
                                  'have with me.',
                    'options': ['She has not had enough time to practise.',
                                'She is unsure about the subject of her talk.',
                                'She feels ready to present but worries about questions.'],
                    'correct': 3},
                   {'q': 2,
                    'type': 'single_choice',
                    'audio': 2,
                    'show': True,
                    'prompt': 'Where will the man stay?',
                    'transcript': 'Speaker 1: [professionally] The city hotel is closest to the conference, but breakfast costs extra. The apartment '
                                  "is cheaper for a week, although it's outside the centre. The guesthouse includes breakfast and is only a "
                                  'ten-minute walk from the venue.\n'
                                  "Speaker 2: [decisively] I don't need a kitchen, and I'd rather not take a bus each morning. The guesthouse sounds "
                                  'best.',
                    'options': ['At the city hotel.', 'At the nearby guesthouse.', 'In the cheaper apartment.'],
                    'correct': 2},
                   {'q': 3,
                    'type': 'single_choice',
                    'audio': 3,
                    'show': True,
                    'prompt': 'Why was the delivery delayed?',
                    'transcript': 'Speaker 1: [concerned] The tracking page said my fridge would arrive this afternoon, but it now shows tomorrow. '
                                  'Has it been left at the warehouse?\n'
                                  'Speaker 2: [apologetically] It left the warehouse on time. A road near your area was closed after an accident, so '
                                  "the driver had to return. We've arranged another vehicle for tomorrow morning.",
                    'options': ['A road closure stopped the driver.',
                                'The item was not ready at the warehouse.',
                                "The customer's address was incorrect."],
                    'correct': 1},
                   {'q': 4,
                    'type': 'single_choice',
                    'audio': 4,
                    'show': True,
                    'prompt': 'What does the man decide to do?',
                    'transcript': "Speaker 1: [professionally] We need someone to support the website project for three months. It isn't a permanent "
                                  "move, but you'd learn a lot about digital marketing.\n"
                                  "Speaker 2: [thoughtfully] I don't want to leave customer service permanently, especially while I'm studying. A "
                                  "short project would be useful, though, and three months is manageable. Yes, I'd like to do it.",
                    'options': ['Apply for a permanent marketing job.', 'Stay away from the website project.', 'Accept the temporary project role.'],
                    'correct': 3}]}}

EXPECTED = {1:5, 2:1, 3:4, 4:4, 5:4}

AUDIO_MAP = {
    (1,1): Path('part_1/track_1.mp3'),
    (1,2): Path('part_1/track_2.mp3'),
    (1,3): Path('part_1/track_3.mp3'),
    (1,4): Path('part_1/track_4.mp3'),
    (2,1): Path('part_2/track_1.mp3'),
    (3,1): Path('part_3/track_1.mp3'),
    (3,2): Path('part_3/track_2.mp3'),
    (3,3): Path('part_3/track_3.mp3'),
    (3,4): Path('part_3/track_4.mp3'),
    (4,1): Path('part_4/track_1.mp3'),
    (4,2): Path('part_4/track_2.mp3'),
    (4,3): Path('part_4/track_3.mp3'),
    (4,4): Path('part_4/track_4.mp3'),
    (5,1): Path('part_5/track_1.mp3'),
    (5,2): Path('part_5/track_2.mp3'),
    (5,3): Path('part_5/track_3.mp3'),
    (5,4): Path('part_5/track_4.mp3'),
}

def locate_audio(part_no, track_no):
    rel = AUDIO_MAP.get((part_no, track_no))
    if rel is None:
        raise RuntimeError(f'No supplied audio mapping for Part {part_no} Track {track_no}.')
    src = PAYLOAD / rel
    if not src.is_file():
        # Fallback case-insensitive search so deployment is robust to ZIP filename case changes.
        target = rel.as_posix().lower()
        for p in PAYLOAD.rglob('*.mp3'):
            if p.relative_to(PAYLOAD).as_posix().lower() == target:
                return p
        raise RuntimeError(f'Missing supplied audio for Part {part_no} Track {track_no}: {rel}')
    return src


def copy_audio(src, part_no, track_no):
    media_root = Path(settings.MEDIA_ROOT)
    rel = Path('question_bank/audio/imported/listening/set_4') / f'part_{part_no}_track_{track_no}.mp3'
    dest = media_root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return rel.as_posix()


def upsert_stimulus(program, part_no, track_no, transcript=''):
    title = f'Listening S4 P{part_no} Track {track_no}'
    matches = list(Stimulus.objects.filter(program=program, title=title).order_by('pk'))
    stimulus = matches[0] if matches else Stimulus(program=program, title=title)
    stimulus.stimulus_type = 'audio'
    stimulus.content = ''
    stimulus.transcript = transcript or ''
    stimulus.source_notes = 'Listening Set 4 import V38.3 · supplied Set 4 audio package · student audio'
    if 'is_active' in names(Stimulus): stimulus.is_active = True
    src = locate_audio(part_no, track_no)
    stimulus.audio_file.name = copy_audio(src, part_no, track_no)
    stimulus.save()
    for dup in matches[1:]:
        if 'is_active' in names(Stimulus):
            dup.is_active = False; dup.save(update_fields=['is_active'])
    return stimulus


def pick_canonical(program, title):
    rows = list(Question.objects.filter(program=program, title=title).order_by('pk'))
    if not rows:
        return Question(program=program, title=title), []
    rows.sort(key=lambda q: (-q.part_assignments.count(), q.pk))
    return rows[0], rows[1:]


def consolidate_duplicate(canonical, dup):
    # Move future-test placements to the canonical row where safe. Existing attempt snapshots are untouched.
    for pq in list(PartQuestion.objects.filter(question=dup).order_by('pk')):
        existing = PartQuestion.objects.filter(part=pq.part, question=canonical).first()
        if existing:
            pq.delete()
            continue
        pq.question = canonical
        try:
            pq.save(update_fields=['question'])
        except Exception:
            pass
    if 'is_active' in names(Question):
        dup.is_active = False
        dup.save(update_fields=['is_active'])


def apply_question(program, part, part_no, spec, stimuli):
    q_no = spec['q']
    title = f'Listening S4 P{part_no} Q{q_no}'
    question, duplicates = pick_canonical(program, title)

    question.skill = 'listening'
    question.question_type = spec['type']
    question.prompt_text = spec.get('prompt','')
    question.show_prompt_text = bool(spec.get('show', True))
    question.stimulus = stimuli.get(spec.get('audio')) if spec.get('audio') else None
    question.prompt_audio = None
    if 'difficulty' in names(Question): question.difficulty = 'medium'
    if 'cefr_level' in names(Question): question.cefr_level = ''
    if 'default_points' in names(Question): question.default_points = 1
    if 'automatic_marking' in names(Question): question.automatic_marking = True
    if 'ai_grading_required' in names(Question): question.ai_grading_required = False
    if 'manual_review_allowed' in names(Question): question.manual_review_allowed = True
    if 'is_active' in names(Question): question.is_active = True
    question.save()

    for dup in duplicates:
        consolidate_duplicate(question, dup)

    QuestionOption.objects.filter(question=question).delete()
    AcceptableAnswer.objects.filter(question=question).delete()
    OrderingItem.objects.filter(question=question).delete()

    if spec['type'] == 'single_choice':
        for idx, text in enumerate(spec['options'], 1):
            QuestionOption.objects.create(question=question, text=text, order=idx, is_correct=(idx == spec['correct']))
    elif spec['type'] == 'short_answer':
        for ans in spec['answers']:
            AcceptableAnswer.objects.create(question=question, answer_text=ans, case_sensitive=False)
    elif spec['type'] == 'ordering':
        items = spec['source_items']
        for pos, label in enumerate(spec['correct_order'], 1):
            OrderingItem.objects.create(question=question, text=items[label], correct_position=pos)

    return question


def archive_source_docs():
    dest = Path(settings.MEDIA_ROOT) / 'question_bank/source_documents/listening/set_4'
    dest.mkdir(parents=True, exist_ok=True)
    source = PAYLOAD / 'LISTENING_SET_4_SOURCE.docx'
    if source.is_file():
        shutil.copy2(source, dest / 'LISTENING_SET_4_SOURCE.docx')
    manifest = dest / 'IMPORT_NOTES_V38_3.txt'
    manifest.write_text(
        'Listening Set 4 imported by V38.3.\n'
        'LISTENING_SET_4_SOURCE.docx is the supplied source document; only SET 4 is imported by this patch.\n'
        '17 supplied MP3 files are mapped to Set 4: Part 1 x4, Part 2 x1, Part 3 x4, Part 4 x4, Part 5 x4.\n'
        'Existing standardized Listening S4 question rows are updated/reused where possible so Mock placements can remain connected.\n',
        encoding='utf-8'
    )


with transaction.atomic():
    program = find_program()
    mock, section, parts = ensure_structure(program)
    archive_source_docs()

    stimuli_by_part = {}
    for part_no in range(1, 6):
        live_tracks = [1] if part_no == 2 else [1,2,3,4]
        stimuli_by_part[part_no] = {}
        for track_no in live_tracks:
            transcript = ''
            if part_no == 2:
                transcript = DATA[2]['transcript']
            else:
                for spec in DATA[part_no]['questions']:
                    if spec.get('audio') == track_no:
                        transcript = spec.get('transcript','')
                        break
            stimuli_by_part[part_no][track_no] = upsert_stimulus(program, part_no, track_no, transcript=transcript)

    canonical_by_part = {}
    for part_no, info in DATA.items():
        part = parts[part_no]
        if 'instructions' in names(TestPart): part.instructions = info['instruction']
        if 'prompt_mode' in names(TestPart): part.prompt_mode = 'audio'
        if 'question_visible' in names(TestPart): part.question_visible = True
        if 'is_active' in names(TestPart): part.is_active = True
        part.save()

        canonical = []
        for spec in info['questions']:
            canonical.append(apply_question(program, part, part_no, spec, stimuli_by_part[part_no]))
        canonical_by_part[part_no] = canonical

    # Replace only Set 4 placements in the shared Listening PRACTICE structure.
    # Set 1 and all other Sets are left in place.
    for part_no, part in parts.items():
        PartQuestion.objects.filter(part=part, question__title__regex=rf'^Listening S4 P{part_no} Q\d+$').delete()
        for q in canonical_by_part[part_no]:
            m = re.search(r' Q(\d+)$', q.title)
            q_no = int(m.group(1))
            PartQuestion.objects.create(part=part, question=q, order=4000 + q_no, is_required=True)
        if 'question_count' in names(TestPart):
            part.question_count = None
            part.save(update_fields=['question_count'])

    expected_titles = {q.title for rows in canonical_by_part.values() for q in rows}
    obsolete = Question.objects.filter(program=program, skill='listening', title__startswith='Listening S4 P').exclude(title__in=expected_titles)
    obsolete_count = 0
    for q in obsolete:
        if 'is_active' in names(Question) and q.is_active:
            q.is_active = False
            q.save(update_fields=['is_active'])
            obsolete_count += 1

print('LISTENING SET 4 IMPORT V38.3 COMPLETE')
print('Program:', program)
print('Practice mock:', mock)
for p in range(1,6):
    rows = canonical_by_part[p]
    audio = len({q.stimulus_id for q in rows if q.stimulus_id})
    print(f'Part {p}: {len(rows)} questions, {audio} student-assigned audio track(s)')
print('Obsolete standardized Set 4 questions archived:', obsolete_count)
print('Source document:', Path(settings.MEDIA_ROOT) / 'question_bank/source_documents/listening/set_4')

