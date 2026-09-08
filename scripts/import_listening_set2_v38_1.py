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

PAYLOAD = Path(os.environ['B1_LISTENING_SET2_PAYLOAD']).resolve()
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


# Source-derived Set 2 data. Audio scripts are kept as admin transcript metadata only.
DATA = {
  1: {
    'instruction': 'You will hear four short recordings as part of one chat. Choose the correct reply for each one. At the end, answer a question about the whole chat.',
    'questions': [
      {'q':1,'type':'single_choice','audio':1,'show':False,'prompt':'','transcript':'Speaker 1: Have you tried the new desk-booking system yet?','options':['Monday is my home-working day.','Yes, I used it to reserve a desk.','The systems team works upstairs.'],'correct':2},
      {'q':2,'type':'single_choice','audio':2,'show':False,'prompt':'','transcript':'Speaker 1: Was it easy to find a space near our team?','options':['I came to work by train.','Our team has six people.','Not at first, but Leo showed me how.'],'correct':3},
      {'q':3,'type':'single_choice','audio':3,'show':False,'prompt':'','transcript':'Speaker 1: Good. Did you manage to book one for Friday?','options':['Yes, beside the window.','Friday is my busiest day.','I usually book it online.'],'correct':1},
      {'q':4,'type':'single_choice','audio':4,'show':False,'prompt':'','transcript':'Speaker 1: Perfect. We can discuss the report there.','options':['I reported it yesterday.','That sounds good.','The discussion lasted an hour.'],'correct':2},
      {'q':5,'type':'single_choice','audio':None,'show':True,'prompt':'What are the colleagues arranging?','options':['Repairing the booking system.','Moving their team to another building.','Working together at a reserved desk on Friday.'],'correct':3},
    ]
  },
  2: {
    'instruction': 'Listen to part of a workplace conversation. Put the five actions the woman completed in the order you hear them.',
    'transcript': """Speaker 1: How did the preparations go while I was at the branch meeting?\nSpeaker 2: Well. I checked the volunteer rota, and everyone can come on Saturday.\nSpeaker 1: That's good. Are the name badges ready?\nSpeaker 2: Yes, I collected them from the print shop this morning.\nSpeaker 1: What about the entrance area?\nSpeaker 2: We moved the welcome desk next to the main doors, so visitors will see it straight away.\nSpeaker 1: And lunch for the helpers?\nSpeaker 2: I called the cafe with the final number of meals. I also emailed a map to each guest speaker.\nSpeaker 1: Excellent.\nSpeaker 2: Tomorrow I'll test the microphones in the hall.""",
    'questions': [
      {'q':1,'type':'ordering','audio':1,'show':True,'prompt':'Put the five completed actions in the order you hear them.',
       'source_items': {
         'A':'Gave the cafe the final meal numbers.',
         'B':'Picked up the printed name badges.',
         'C':'Sent location information to the guest speakers.',
         'D':'Changed the position of the welcome desk.',
         'E':'Confirmed which volunteers could attend.',
       },
       'correct_order':['E','B','D','A','C']}
    ]
  },
  3: {
    'instruction':'You will hear four short recordings. Listen and write the correct information in each gap.',
    'questions':[
      {'q':1,'type':'short_answer','audio':1,'show':True,'prompt':'Repair reference: __________','transcript':"Speaker 1: Hello. I'm calling about a coffee machine I left for repair.\nSpeaker 2: Certainly. Do you have the repair reference?\nSpeaker 1: Yes. It's five, eight, three, one, zero, four.\nSpeaker 2: Thank you. I'll check its progress.",'answers':['583104']},
      {'q':2,'type':'short_answer','audio':2,'show':True,'prompt':'Surname: __________','transcript':"Speaker 1: Hi. I've come to collect my new membership card.\nSpeaker 2: Of course. What's your surname?\nSpeaker 1: Banerjee. B-A-N-E-R-J-E-E.\nSpeaker 2: Thanks. Here it is.",'answers':['Banerjee']},
      {'q':3,'type':'short_answer','audio':3,'show':True,'prompt':'The safety inspection will now take place on __________.','transcript':"Speaker 1: Facilities office. Daniel speaking.\nSpeaker 2: Hi, Daniel. It's Salma from the west building. Our safety inspection was arranged for the fifth of November, but the engineer can't come then. Could we move it to the twelfth of November?\nSpeaker 1: Yes, the twelfth is available. I'll change it now.",'answers':['12 November']},
      {'q':4,'type':'short_answer','audio':4,'show':True,'prompt':"The customer's PIN is __________.",'transcript':"Speaker 1: I need to change the phone number on my account.\nSpeaker 2: I can help with that. First, what's your five-digit telephone-banking PIN?\nSpeaker 1: Nine, two, six, four, zero.\nSpeaker 2: Thank you. Now, could you confirm your postcode?",'answers':['92640']},
    ]
  },
  4: {
    'instruction':'You will hear four short recordings. For each one, choose the correct answer.',
    'questions':[
      {'q':1,'type':'single_choice','audio':1,'show':True,'prompt':'What will the customer receive?','transcript':"Speaker 1: I bought this lamp yesterday as a present. Could I have a gift receipt?\nSpeaker 2: Our receipt printer isn't working, but I can email one to you now.\nSpeaker 1: That would be perfect.",'options':['A paper receipt later.','A refund for the lamp.','A gift receipt by email.'],'correct':3},
      {'q':2,'type':'single_choice','audio':2,'show':True,'prompt':'How will the man reach the training room?','transcript':"Speaker 1: Is the training room still on the fourth floor?\nSpeaker 2: Yes, but the lift is being serviced today. The stairs are behind the cafe.\nSpeaker 1: All right. I'll use those.",'options':['By taking the stairs.','By using the lift.','By walking through the cafe.'],'correct':1},
      {'q':3,'type':'single_choice','audio':3,'show':True,'prompt':'What problem does the woman have?','transcript':"Speaker 1: The self-service machine won't let me borrow this book.\nSpeaker 2: Let me see. Your library card expired last week.\nSpeaker 1: Oh, I didn't notice. Can I renew it here?",'options':['The machine cannot read the book.','Her library membership has expired.','She has brought the wrong library card.'],'correct':2},
      {'q':4,'type':'single_choice','audio':4,'show':True,'prompt':'What has changed?','transcript':"Speaker 1: Is the photography class still in the park this afternoon?\nSpeaker 2: The time hasn't changed, but the forecast says heavy rain. We're meeting in Studio Two instead.\nSpeaker 1: Thanks. I'll go straight there.",'options':['The class time.','The class topic.','The class location.'],'correct':3},
    ]
  },
  5: {
    'instruction':'You will hear four longer recordings. For each one, choose the correct answer.',
    'questions':[
      {'q':1,'type':'single_choice','audio':1,'show':True,'prompt':'How does the man feel about mentoring the new employee?','transcript':"Speaker 1: Would you be willing to mentor the new receptionist next month? You explain our systems very clearly.\nSpeaker 2: I'm glad you asked. I enjoy helping new colleagues, but my month-end reports are due at the same time. I'm not sure I'll have enough time for both.\nSpeaker 1: We can give one of those reports to Daniel, so it shouldn't be a problem.",'options':['He is pleased but concerned about his workload.','He thinks the receptionist has already been trained.','He would prefer not to help another employee.'],'correct':1},
      {'q':2,'type':'single_choice','audio':2,'show':True,'prompt':'Which option will the man choose for now?','transcript':"Speaker 1: The annual membership works out at twenty pounds a month. A monthly membership is twenty-eight, or you can buy an eight-pound day pass whenever you visit.\nSpeaker 2: I travel a lot for work, so some months I might only come twice. I'll begin with the day passes and see how often I use the gym.",'options':['An annual membership.','A monthly membership.','Individual day passes.'],'correct':3},
      {'q':3,'type':'single_choice','audio':3,'show':True,'prompt':'Why can the man not attend the interview as planned?','transcript':"Speaker 1: My online interview is at two, and the link works, but my laptop camera stopped working this morning. The invitation says video must be on.\nSpeaker 2: We can't do the interview by phone, but I can move it to tomorrow if you need time to borrow another computer.",'options':['He has forgotten the interview time.','His computer camera is not working.','The interviewer has cancelled the call.'],'correct':2},
      {'q':4,'type':'single_choice','audio':4,'show':True,'prompt':'Why does the man decide not to buy the desk?','transcript':"Speaker 1: This desk is reduced by thirty percent, and it has the two drawers you wanted. Would you like us to arrange delivery?\nSpeaker 2: The price is excellent, and I like the style, but I measured my study this morning. The desk is fifteen centimetres too wide for the only free wall, so I'll leave it.",'options':['It will not fit in his room.','It does not provide enough storage.','It costs more than he expected.'],'correct':1},
    ]
  }
}

EXPECTED = {1:5, 2:1, 3:4, 4:4, 5:4}

AUDIO_MAP = {
    (1,1): Path('part 1/Part 1.mp3'),
    (1,2): Path('part 1/part 2.mp3'),
    (1,3): Path('part 1/Part 3.mp3'),
    (1,4): Path('part 1/Part 4.mp3'),
    (2,1): Path('part 2/Part 2.mp3'),
    (3,1): Path('Part 3/part 3 1.mp3'),
    (3,2): Path('Part 3/part 3 2.mp3'),
    (3,3): Path('Part 3/Part 3 3.mp3'),
    (3,4): Path('Part 3/part 3 4.mp3'),
    (4,1): Path('Part 4/part 4 1.mp3'),
    (4,2): Path('Part 4/Part 4 2.mp3'),
    (4,3): Path('Part 4/Part 4 3.mp3'),
    (4,4): Path('Part 4/Part 4 4.mp3'),
    (5,1): Path('Part 5/Part 5 1.mp3'),
    (5,2): Path('Part 5/Part 5 2.mp3'),
    (5,3): Path('Part 5/part 5 3.mp3'),
    (5,4): Path('Part 5/part 5 4.mp3'),
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
    rel = Path('question_bank/audio/imported/listening/set_2') / f'part_{part_no}_track_{track_no}.mp3'
    dest = media_root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return rel.as_posix()


def upsert_stimulus(program, part_no, track_no, transcript=''):
    title = f'Listening S2 P{part_no} Track {track_no}'
    matches = list(Stimulus.objects.filter(program=program, title=title).order_by('pk'))
    stimulus = matches[0] if matches else Stimulus(program=program, title=title)
    stimulus.stimulus_type = 'audio'
    stimulus.content = ''
    stimulus.transcript = transcript or ''
    stimulus.source_notes = 'Listening Set 2 import V38.1 · supplied Set 2 audio package · student audio'
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
    title = f'Listening S2 P{part_no} Q{q_no}'
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
    dest = Path(settings.MEDIA_ROOT) / 'question_bank/source_documents/listening/set_2'
    dest.mkdir(parents=True, exist_ok=True)
    source = PAYLOAD / 'CAMBRIDGE UPSKILL.docx'
    if source.is_file():
        shutil.copy2(source, dest / 'CAMBRIDGE_UPSKILL_SETS_2_TO_11_SOURCE.docx')
    manifest = dest / 'IMPORT_NOTES_V38_1.txt'
    manifest.write_text(
        'Listening Set 2 imported by V38.1.\n'
        'CAMBRIDGE_UPSKILL_SETS_2_TO_11_SOURCE.docx is the supplied source document; only SET 2 is imported by this patch.\n'
        '17 supplied MP3 files are mapped to Set 2: Part 1 x4, Part 2 x1, Part 3 x4, Part 4 x4, Part 5 x4.\n'
        'Existing standardized Listening S2 question rows are updated/reused where possible so Mock placements can remain connected.\n',
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

    # Replace only Set 2 placements in the shared Listening PRACTICE structure.
    # Set 1 and all other Sets are left in place.
    for part_no, part in parts.items():
        PartQuestion.objects.filter(part=part, question__title__regex=rf'^Listening S2 P{part_no} Q\d+$').delete()
        for q in canonical_by_part[part_no]:
            m = re.search(r' Q(\d+)$', q.title)
            q_no = int(m.group(1))
            PartQuestion.objects.create(part=part, question=q, order=2000 + q_no, is_required=True)
        if 'question_count' in names(TestPart):
            part.question_count = None
            part.save(update_fields=['question_count'])

    expected_titles = {q.title for rows in canonical_by_part.values() for q in rows}
    obsolete = Question.objects.filter(program=program, skill='listening', title__startswith='Listening S2 P').exclude(title__in=expected_titles)
    obsolete_count = 0
    for q in obsolete:
        if 'is_active' in names(Question) and q.is_active:
            q.is_active = False
            q.save(update_fields=['is_active'])
            obsolete_count += 1

print('LISTENING SET 2 IMPORT V38.1 COMPLETE')
print('Program:', program)
print('Practice mock:', mock)
for p in range(1,6):
    rows = canonical_by_part[p]
    audio = len({q.stimulus_id for q in rows if q.stimulus_id})
    print(f'Part {p}: {len(rows)} questions, {audio} student-assigned audio track(s)')
print('Obsolete standardized Set 2 questions archived:', obsolete_count)
print('Source document:', Path(settings.MEDIA_ROOT) / 'question_bank/source_documents/listening/set_2')

