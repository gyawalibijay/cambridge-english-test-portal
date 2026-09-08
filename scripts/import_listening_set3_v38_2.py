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

PAYLOAD = Path(os.environ['B1_LISTENING_SET3_PAYLOAD']).resolve()
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


# Source-derived Set 3 data. Audio scripts are kept as admin transcript metadata only.
DATA = {1: {'instruction': 'You will hear four short recordings as part of one chat. Choose the correct reply for each one. At the end, answer a question '
                    'about the whole chat.',
     'questions': [{'q': 1,
                    'type': 'single_choice',
                    'audio': 1,
                    'show': False,
                    'prompt': '',
                    'transcript': "Speaker 1: [casually interested] Did you go to the supplier's new showroom yesterday?",
                    'options': ['They open at nine.', 'The showroom is near the station.', 'Yes, I took the afternoon bus.'],
                    'correct': 3},
                   {'q': 2,
                    'type': 'single_choice',
                    'audio': 2,
                    'show': False,
                    'prompt': '',
                    'transcript': 'Speaker 1: [curious] What did you think of their recycled packaging?',
                    'options': ['It looked strong and well designed.', 'No, we have enough wrapping paper.', 'Their new designer starts tomorrow.'],
                    'correct': 1},
                   {'q': 3,
                    'type': 'single_choice',
                    'audio': 3,
                    'show': False,
                    'prompt': '',
                    'transcript': 'Speaker 1: [thoughtfully] Do you think we should order a sample?',
                    'options': ['The supplier has three branches.', 'Yes, before we make a final decision.', 'The last order arrived on Tuesday.'],
                    'correct': 2},
                   {'q': 4,
                    'type': 'single_choice',
                    'audio': 4,
                    'show': False,
                    'prompt': '',
                    'transcript': "Speaker 1: [decisively] I'll ask for one this morning.",
                    'options': ['I asked her yesterday.', 'Mornings are usually quiet.', 'Great. Let me know when it arrives.'],
                    'correct': 3},
                   {'q': 5,
                    'type': 'single_choice',
                    'audio': None,
                    'show': True,
                    'prompt': 'What are the colleagues considering?',
                    'transcript': '',
                    'options': ['Trying a new type of product packaging.',
                                'Visiting the showroom for a second time.',
                                'Changing the bus route to the supplier.'],
                    'correct': 1}]},
 2: {'instruction': 'Listen to part of a workplace conversation. Put the five actions the woman completed in the order you hear them.',
     'transcript': 'Speaker 1: [interested] Is everything ready for the online shop to open?\n'
                   'Speaker 2: [confidently] Nearly. I tested the checkout page on three different phones, and it worked each time.\n'
                   'Speaker 1: [prompting] Good. What about the new products?\n'
                   'Speaker 2: [matter-of-factly] I photographed all twelve of them. I added the delivery prices after that because they were '
                   'missing from the product pages.\n'
                   'Speaker 1: [curious] Has anyone outside the office tried the site?\n'
                   'Speaker 2: [assured] Yes. I invited three regular customers to test it. They found two small errors, so I sent a list of those '
                   'to the developer.\n'
                   'Speaker 1: [satisfied] Excellent. Are you announcing the launch today?\n'
                   "Speaker 2: [forward-looking] I'll put it on social media tomorrow morning.",
     'questions': [{'q': 1,
                    'type': 'ordering',
                    'audio': 1,
                    'show': True,
                    'prompt': 'Put the five completed actions in the order you hear them.',
                    'source_items': {'A': 'Put the delivery charges on the product pages.',
                                     'B': 'Reported website errors to the developer.',
                                     'C': 'Checked that the payment process worked on phones.',
                                     'D': 'Asked regular customers to try the website.',
                                     'E': 'Took pictures of the new products.'},
                    'correct_order': ['C', 'E', 'A', 'D', 'B']}]},
 3: {'instruction': 'You will hear four short recordings. Listen and write the correct information in each gap.',
     'questions': [{'q': 1,
                    'type': 'short_answer',
                    'audio': 1,
                    'show': True,
                    'prompt': 'Booking reference: __________',
                    'transcript': "Speaker 1: [politely] I'm calling because my concert tickets haven't arrived by email.\n"
                                  "Speaker 2: [helpfully] I'll look into that. What's the booking reference?\n"
                                  'Speaker 1: [carefully, reading individual digits] Seven, three, one, two, five, eight.\n'
                                  "Speaker 2: [reassuringly] Thank you. I've found your booking.",
                    'answers': ['731258']},
                   {'q': 2,
                    'type': 'short_answer',
                    'audio': 2,
                    'show': True,
                    'prompt': 'Surname: __________',
                    'transcript': "Speaker 1: [politely] Hello. There's a parcel here for me to collect.\n"
                                  'Speaker 2: [professionally] Could I have your surname, please?\n'
                                  'Speaker 1: [clearly, then spelling] Collins. C-O-L-L-I-N-S.\n'
                                  'Speaker 2: [warmly] Thanks. One moment.',
                    'answers': ['Collins']},
                   {'q': 3,
                    'type': 'short_answer',
                    'audio': 3,
                    'show': True,
                    'prompt': 'The training will now take place on __________.',
                    'transcript': 'Speaker 1: [businesslike] We booked the customer-service training for the thirtieth of January, but too many '
                                  'staff are on leave that day. Is the fourth of February available instead?\n'
                                  "Speaker 2: [confirming] Yes, I can come on the fourth. I'll send you a new confirmation.",
                    'answers': ['4 February']},
                   {'q': 4,
                    'type': 'short_answer',
                    'audio': 4,
                    'show': True,
                    'prompt': '---',
                    'transcript': "Speaker 1: [calmly] I can't open my staff expenses account.\n"
                                  'Speaker 2: [professionally] I can reset it. First, please tell me your five-digit security PIN.\n'
                                  'Speaker 1: [carefully, reading individual digits] Five, zero, eight, one, seven.\n'
                                  'Speaker 2: [neutral] Thank you. Now I need your employee number.\n'
                                  "The employee's PIN is __________.",
                    'answers': ['50817']}]},
 4: {'instruction': 'You will hear four short recordings. For each one, choose the correct answer.',
     'questions': [{'q': 1,
                    'type': 'single_choice',
                    'audio': 1,
                    'show': True,
                    'prompt': 'What does the man want to do?',
                    'transcript': "Speaker 1: [concerned] I placed an order this morning, but I've just noticed it has my old address.\n"
                                  "Speaker 2: [reassuringly] It hasn't left our warehouse yet, so I can send it to your new address.\n"
                                  "Speaker 1: [relieved] Please do. I don't want to cancel the order.",
                    'options': ['Change where the parcel will be delivered.',
                                'Cancel the order before it is sent.',
                                'Collect the parcel from the warehouse.'],
                    'correct': 1},
                   {'q': 2,
                    'type': 'single_choice',
                    'audio': 2,
                    'show': True,
                    'prompt': 'What will the receptionist do?',
                    'transcript': "Speaker 1: [politely frustrated] My room key worked this morning, but it won't open the door now.\n"
                                  "Speaker 2: [apologetically] I'm sorry. It may have stopped working near your phone. I'll make another key for "
                                  'you.\n'
                                  'Speaker 1: [grateful] Thank you.',
                    'options': ["Check the guest's phone.", 'Open the room himself.', 'Provide a replacement key.'],
                    'correct': 3},
                   {'q': 3,
                    'type': 'single_choice',
                    'audio': 3,
                    'show': True,
                    'prompt': 'Why does the woman not order the soup?',
                    'transcript': "Speaker 1: [inquiring] Is today's vegetable soup suitable for someone who can't have milk?\n"
                                  "Speaker 2: [apologetically] I'm afraid not. The vegetables don't contain dairy, but the cook adds cream at the "
                                  'end.\n'
                                  "Speaker 1: [decisively] Then I'll choose the salad.",
                    'options': ['It has no vegetables.', 'It contains an ingredient she cannot have.', 'It is no longer available.'],
                    'correct': 2},
                   {'q': 4,
                    'type': 'single_choice',
                    'audio': 4,
                    'show': True,
                    'prompt': 'What arrangement is made?',
                    'transcript': 'Speaker 1: [professionally] Your appointment is currently Monday afternoon. We have a cancellation on Thursday '
                                  'morning if you prefer.\n'
                                  'Speaker 2: [pleased] Thursday morning is much easier for me. Please move it.',
                    'options': ['The appointment is moved to Thursday morning.',
                                'The appointment remains on Monday afternoon.',
                                'The appointment is cancelled completely.'],
                    'correct': 1}]},
 5: {'instruction': 'You will hear four longer recordings. For each one, choose the correct answer.',
     'questions': [{'q': 1,
                    'type': 'single_choice',
                    'audio': 1,
                    'show': True,
                    'prompt': 'How does the man feel about working from home?',
                    'transcript': 'Speaker 1: [curiously] How are you finding working from home three days a week? You used to dislike the long '
                                  'journey to the office.\n'
                                  'Speaker 2: [thoughtfully] Not travelling every morning is excellent, and I can concentrate well at home. I do '
                                  "miss talking to the team, though. Video calls are useful, but they don't feel quite the same as sharing an "
                                  'office.',
                    'options': ['He wants to work at home every day.',
                                'He likes some benefits but misses his colleagues.',
                                'He finds it harder to concentrate there.'],
                    'correct': 2},
                   {'q': 2,
                    'type': 'single_choice',
                    'audio': 2,
                    'show': True,
                    'prompt': 'What food does the organiser choose?',
                    'transcript': 'Speaker 1: [explaining] We need lunch for forty people. Several guests are vegetarian, and two cannot eat dairy '
                                  "products. Sandwiches would be cheaper, but I'm worried there won't be enough choice.\n"
                                  'Speaker 2: [reassuringly] Our hot buffet includes two vegetarian dishes and a dairy-free rice dish. Everything is '
                                  'clearly labelled, and it is still within your budget.\n'
                                  "Speaker 1: [decisively] That sounds safest. Let's have the hot buffet.",
                    'options': ['A hot buffet with suitable choices.', 'A cheaper selection of sandwiches.', 'A separate meal for every guest.'],
                    'correct': 1},
                   {'q': 3,
                    'type': 'single_choice',
                    'audio': 3,
                    'show': True,
                    'prompt': 'Why can the customer not receive a refund?',
                    'transcript': "Speaker 1: [politely] I'd like to return this jacket. It hasn't been worn, and I still have the receipt.\n"
                                  'Speaker 2: [apologetically] The jacket is in perfect condition, but you bought it six weeks ago. Our returns '
                                  "period is thirty days. We can exchange it for another size, but we can't give a refund now.",
                    'options': ['She has lost the receipt.', 'The jacket has been worn.', 'She is outside the refund period.'],
                    'correct': 3},
                   {'q': 4,
                    'type': 'single_choice',
                    'audio': 4,
                    'show': True,
                    'prompt': 'Why did the woman change classes?',
                    'transcript': 'Speaker 1: [curiously] I thought you were taking the Wednesday evening design course. Why did you change to '
                                  'Saturday mornings?\n'
                                  'Speaker 2: [explaining] My manager changed my work schedule, so I now finish late every Wednesday. The tutor is '
                                  'the same on Saturdays, and the college is actually quieter then, so the new class should be fine.',
                    'options': ['She wanted a different tutor.',
                                'Her new work hours caused a problem.',
                                'The college is closed on Wednesday evenings.'],
                    'correct': 2}]}}

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
    rel = Path('question_bank/audio/imported/listening/set_3') / f'part_{part_no}_track_{track_no}.mp3'
    dest = media_root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return rel.as_posix()


def upsert_stimulus(program, part_no, track_no, transcript=''):
    title = f'Listening S3 P{part_no} Track {track_no}'
    matches = list(Stimulus.objects.filter(program=program, title=title).order_by('pk'))
    stimulus = matches[0] if matches else Stimulus(program=program, title=title)
    stimulus.stimulus_type = 'audio'
    stimulus.content = ''
    stimulus.transcript = transcript or ''
    stimulus.source_notes = 'Listening Set 3 import V38.2 · supplied Set 3 audio package · student audio'
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
    title = f'Listening S3 P{part_no} Q{q_no}'
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
    dest = Path(settings.MEDIA_ROOT) / 'question_bank/source_documents/listening/set_3'
    dest.mkdir(parents=True, exist_ok=True)
    source = PAYLOAD / 'LISTENING_SET_3_SOURCE.docx'
    if source.is_file():
        shutil.copy2(source, dest / 'LISTENING_SET_3_SOURCE.docx')
    manifest = dest / 'IMPORT_NOTES_V38_2.txt'
    manifest.write_text(
        'Listening Set 3 imported by V38.2.\n'
        'LISTENING_SET_3_SOURCE.docx is the supplied source document; only SET 3 is imported by this patch.\n'
        '17 supplied MP3 files are mapped to Set 3: Part 1 x4, Part 2 x1, Part 3 x4, Part 4 x4, Part 5 x4.\n'
        'Existing standardized Listening S3 question rows are updated/reused where possible so Mock placements can remain connected.\n',
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

    # Replace only Set 3 placements in the shared Listening PRACTICE structure.
    # Set 1 and all other Sets are left in place.
    for part_no, part in parts.items():
        PartQuestion.objects.filter(part=part, question__title__regex=rf'^Listening S3 P{part_no} Q\d+$').delete()
        for q in canonical_by_part[part_no]:
            m = re.search(r' Q(\d+)$', q.title)
            q_no = int(m.group(1))
            PartQuestion.objects.create(part=part, question=q, order=3000 + q_no, is_required=True)
        if 'question_count' in names(TestPart):
            part.question_count = None
            part.save(update_fields=['question_count'])

    expected_titles = {q.title for rows in canonical_by_part.values() for q in rows}
    obsolete = Question.objects.filter(program=program, skill='listening', title__startswith='Listening S3 P').exclude(title__in=expected_titles)
    obsolete_count = 0
    for q in obsolete:
        if 'is_active' in names(Question) and q.is_active:
            q.is_active = False
            q.save(update_fields=['is_active'])
            obsolete_count += 1

print('LISTENING SET 3 IMPORT V38.2 COMPLETE')
print('Program:', program)
print('Practice mock:', mock)
for p in range(1,6):
    rows = canonical_by_part[p]
    audio = len({q.stimulus_id for q in rows if q.stimulus_id})
    print(f'Part {p}: {len(rows)} questions, {audio} student-assigned audio track(s)')
print('Obsolete standardized Set 3 questions archived:', obsolete_count)
print('Source document:', Path(settings.MEDIA_ROOT) / 'question_bank/source_documents/listening/set_3')

