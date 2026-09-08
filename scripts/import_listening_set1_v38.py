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

PAYLOAD = Path(os.environ['B1_LISTENING_SET1_PAYLOAD']).resolve()
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


# Source-derived Set 1 data. The transcript is administrative only and is not shown automatically.
DATA = {
  1: {
    'instruction': 'You will hear four short recordings as part of one chat. Choose the correct reply for each one. Then answer Question 5 about the whole chat.',
    'questions': [
      {'q':1,'type':'single_choice','audio':1,'show':False,'prompt':'','transcript':'COLLEAGUE: Did the courier arrive before you left yesterday?','options':['I normally leave at five.','The front desk closes at five.','Yes, just before four.'],'correct':3},
      {'q':2,'type':'single_choice','audio':2,'show':False,'prompt':'','transcript':'COLLEAGUE: Good. Were all the display stands in the delivery?','options':['One small stand was missing.','They look very modern.','I signed for the delivery.'],'correct':1},
      {'q':3,'type':'single_choice','audio':3,'show':False,'prompt':'','transcript':"COLLEAGUE: Oh dear. Have you told the supplier about it?",'options':["The supplier's office is nearby.",'Yes, I sent them a photo this morning.','The delivery arrived early yesterday.'],'correct':2},
      {'q':4,'type':'single_choice','audio':4,'show':False,'prompt':'','transcript':'COLLEAGUE: Great. Let me know when they reply.','options':["I'll check my train time.",'You replied yesterday.','Of course.'],'correct':3},
      {'q':5,'type':'single_choice','audio':None,'show':True,'prompt':'What problem are the colleagues discussing?','options':['The courier arrived too late.','An item was missing from a delivery.','A photograph could not be opened.'],'correct':2},
    ]
  },
  2: {
    'instruction': 'Listen to part of a workplace conversation. Put the five actions the woman completed in the order you hear them.',
    'transcript': """MAN: How did things go with the staff training day?\nWOMAN: Pretty well. I spoke to the trainer and confirmed the equipment she needs.\nMAN: Good. We were worried about the projector.\nWOMAN: That's sorted. I also reserved the large conference room because more people registered than expected.\nMAN: Right. What about the numbers?\nWOMAN: I checked the attendance list and marked who needed a vegetarian lunch.\nMAN: And the food?\nWOMAN: I phoned the catering company with the final numbers, and they confirmed the order.\nMAN: Excellent. Did you tell the department heads about the new room?\nWOMAN: Yes, I emailed them the updated timetable and room details. Tomorrow I'll put signs by reception.\nMAN: Great, thanks.""",
    'questions': [
      {'q':1,'type':'ordering','audio':1,'show':True,'prompt':'Put the five completed actions in the order you hear them.',
       'source_items': {
         'A':'Contacted the caterer with the final numbers.',
         'B':'Reserved a larger room.',
         'C':'Sent managers updated event information.',
         'D':'Confirmed the equipment with the trainer.',
         'E':'Reviewed attendance and lunch requirements.',
       },
       'correct_order':['D','B','E','A','C']}
    ]
  },
  3: {
    'instruction':'You will hear four short recordings. Listen and write the correct information in each gap.',
    'questions':[
      {'q':1,'type':'short_answer','audio':1,'show':True,'prompt':'Delivery reference: __________','transcript':"CUSTOMER: Hello. My replacement headset was due today, but it hasn't arrived.\nAGENT: Do you have the delivery reference?\nCUSTOMER: Yes. It's four, seven, two, nine, zero, six.\nAGENT: Thank you. I'll check that now.",'answers':['472906']},
      {'q':2,'type':'short_answer','audio':2,'show':True,'prompt':'Surname on the parcel: __________','transcript':"CUSTOMER: Hi. I'm here to collect a parcel for my office.\nCLERK: Certainly. What's the surname on the parcel?\nCUSTOMER: Mehta. That's M-E-H-T-A.\nCLERK: Thanks. I'll get it for you.",'answers':['Mehta']},
      {'q':3,'type':'short_answer','audio':3,'show':True,'prompt':'Nita requests ten days of leave, now beginning __________.','transcript':"HR OFFICER: Good afternoon. Mark Wilson, Human Resources.\nNITA: Hello, Mark. It's Nita Rao from Finance. I booked ten days off beginning on the twenty-second of September, but I need to change the dates. I'd still like ten days, now starting on the sixth of October. Is that all right?\nHR OFFICER: I'll check with your manager and call you back.",'answers':['6 October','6th October','October 6','October 6th']},
      {'q':4,'type':'short_answer','audio':4,'show':True,'prompt':"The customer's PIN is __________.",'transcript':"CUSTOMER: I need to update the address on my account.\nAGENT: Of course. Can I have your customer number?\nCUSTOMER: I don't have it with me.\nAGENT: That's all right. What's your five-digit PIN?\nCUSTOMER: Seven, four, one, two, six.\nAGENT: And your date of birth?\nCUSTOMER: The third of December, nineteen ninety-one.\nAGENT: Thank you. I've found your account.",'answers':['74126']},
    ]
  },
  4: {
    'instruction':'You will hear four short recordings. For each one, choose the correct answer.',
    'questions':[
      {'q':1,'type':'single_choice','audio':1,'show':True,'prompt':'What will the woman do?','transcript':"MAN: The customer left another message about the damaged order.\nWOMAN: I was going to call her after lunch.\nMAN: She says the delivery driver is still outside and needs an answer now.\nWOMAN: In that case, I'll ring her straight away.",'options':['Call the customer immediately.','Wait until after lunch.','Speak to the delivery driver.'],'correct':1},
      {'q':2,'type':'single_choice','audio':2,'show':True,'prompt':'What is the man going to do?','transcript':"WOMAN: Have you seen Priya? The fire-safety talk is about to start.\nMAN: I thought it was online.\nWOMAN: No, they've moved it to the ground-floor hall. I'm heading down now.\nMAN: Thanks. I'll come with you.",'options':['Join the talk online.','Contact Priya.','Go to the ground-floor hall.'],'correct':3},
      {'q':3,'type':'single_choice','audio':3,'show':True,'prompt':'What problem does the man have?','transcript':"MAN: Excuse me. I paid for parking through the app, but the barrier won't open.\nATTENDANT: Does the app show that your payment was accepted?\nMAN: Yes, but I've just noticed that I entered my old car registration.\nATTENDANT: That's the problem. I can correct it for you.",'options':['The parking barrier is broken.','He used the wrong car registration.','He has not paid for parking.'],'correct':2},
      {'q':4,'type':'single_choice','audio':4,'show':True,'prompt':'What has changed?','transcript':"MANAGER: The client visit was planned for Thursday afternoon, wasn't it?\nASSISTANT: It was, but their flight now arrives on Friday morning.\nMANAGER: All right. Keep the same tour and lunch, but move everything to Friday after they arrive.\nASSISTANT: I'll update the calendar.",'options':['The day of the client visit.','The place chosen for lunch.','The length of the factory tour.'],'correct':1},
    ]
  },
  5: {
    'instruction':'You will hear four longer recordings. For each one, choose the correct answer.',
    'questions':[
      {'q':1,'type':'single_choice','audio':1,'show':True,'prompt':'How does the woman feel about the course?','transcript':"MAN: Your first evening class is tomorrow. Are you looking forward to it?\nWOMAN: Yes, especially the practical work. I've already read a little about the subject. I'm just worried about speaking in front of the whole group. I don't know how many presentations we'll have to do.\nMAN: Probably only a few, and the tutor will help you prepare.",'options':['Bored because she already knows the subject.','Interested but anxious about giving presentations.','Disappointed that the course mainly involves reading.'],'correct':2},
      {'q':2,'type':'single_choice','audio':2,'show':True,'prompt':'How will the woman travel to Lakeside?','transcript':"TRAVEL AGENT: Are you still thinking about taking the coach to Lakeside?\nWOMAN: Possibly, but six hours is a long journey.\nTRAVEL AGENT: The train is faster, although it costs more. There's also a shared-car service leaving at eight.\nWOMAN: I don't want to travel in a car with people I haven't met. I can pay the extra, so please book the train.",'options':['By coach.','By shared car.','By train.'],'correct':3},
      {'q':3,'type':'single_choice','audio':3,'show':True,'prompt':'Why is the employee unable to take the laptop?','transcript':"EMPLOYEE: Hello. I've come to collect the laptop my colleague left here for repair.\nTECHNICIAN: It's fixed, but I can't return it yet. Your colleague asked us to protect the files with a password.\nEMPLOYEE: I have the repair receipt here.\nTECHNICIAN: Thanks, but I need the password as well. Could you ask your colleague and come back?",'options':['He does not know the required password.','The laptop has not been repaired.','He has forgotten the repair receipt.'],'correct':1},
      {'q':4,'type':'single_choice','audio':4,'show':True,'prompt':'Why did the woman decide not to take the flat?','transcript':"MAN: Did you accept the flat near your office?\nWOMAN: I nearly did. The rent was reasonable, and the rooms were bright, but the landlord only offered a six-month contract. I need somewhere for at least a year, so I turned it down. I'm viewing another place on Saturday.",'options':['It was too far from her office.','The rental contract was too short.','The rooms did not have enough light.'],'correct':2},
    ]
  }
}

EXPECTED = {1:5, 2:1, 3:4, 4:4, 5:4}


def locate_audio(part_no, track_no):
    candidates = []
    patt = re.compile(rf'^part\s*{part_no}\s+{track_no}\.mp3$', re.I)
    for p in PAYLOAD.rglob('*.mp3'):
        if patt.match(p.name):
            parent = p.parent.name.lower().replace('_',' ')
            if re.search(rf'part\s*{part_no}\b', parent):
                candidates.append(p)
    if not candidates:
        raise RuntimeError(f'Missing supplied audio for Part {part_no} Track {track_no}.')
    candidates.sort(key=lambda p: (len(str(p)), str(p).lower()))
    return candidates[0]


def copy_audio(src, part_no, track_no):
    media_root = Path(settings.MEDIA_ROOT)
    rel = Path('question_bank/audio/imported/listening/set_1') / f'part_{part_no}_track_{track_no}.mp3'
    dest = media_root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return rel.as_posix()


def upsert_stimulus(program, part_no, track_no, transcript='', reference=False):
    title = f'Listening S1 P{part_no} Track {track_no}'
    matches = list(Stimulus.objects.filter(program=program, title=title).order_by('pk'))
    stimulus = matches[0] if matches else Stimulus(program=program, title=title)
    stimulus.stimulus_type = 'audio'
    stimulus.content = ''
    stimulus.transcript = transcript or ''
    stimulus.source_notes = (
        'Listening Set 1 import V38.0 · supplied audio package · '
        + ('reference/alternate track retained; not student-assigned' if reference else 'student audio')
    )
    if 'is_active' in names(Stimulus): stimulus.is_active = True
    src = locate_audio(part_no, track_no)
    stimulus.audio_file.name = copy_audio(src, part_no, track_no)
    stimulus.save()
    for dup in matches[1:]:
        # Keep duplicates as inactive history instead of deleting potentially referenced rows.
        if 'is_active' in names(Stimulus):
            dup.is_active = False; dup.save(update_fields=['is_active'])
    return stimulus


def pick_canonical(program, title):
    rows = list(Question.objects.filter(program=program, title=title).order_by('pk'))
    if not rows:
        return Question(program=program, title=title), []
    # Prefer the record with existing placements to preserve current Mock links where possible.
    rows.sort(key=lambda q: (-q.part_assignments.count(), q.pk))
    return rows[0], rows[1:]


def consolidate_duplicate(canonical, dup):
    # Move future-test placements from duplicate to canonical when possible; attempts stay untouched.
    for pq in list(PartQuestion.objects.filter(question=dup).order_by('pk')):
        existing = PartQuestion.objects.filter(part=pq.part, question=canonical).first()
        if existing:
            pq.delete()
            continue
        pq.question = canonical
        try:
            pq.save(update_fields=['question'])
        except Exception:
            # Keep the placement but make the duplicate invisible to future Set discovery.
            pass
    if 'is_active' in names(Question):
        dup.is_active = False
        dup.save(update_fields=['is_active'])


def apply_question(program, part, part_no, spec, stimuli):
    q_no = spec['q']
    title = f'Listening S1 P{part_no} Q{q_no}'
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
    dest = Path(settings.MEDIA_ROOT) / 'question_bank/source_documents/listening/set_1'
    dest.mkdir(parents=True, exist_ok=True)
    for src_name, dest_name in [
        ('LISTENING.docx', 'LISTENING_SET_1_SOURCE.docx'),
        ('CAMBRIDGE UPSKILL sceipt and answer.docx', 'CAMBRIDGE_UPSKILL_script_and_answer_SUPPLIED.docx'),
    ]:
        matches = list(PAYLOAD.rglob(src_name))
        if matches:
            shutil.copy2(matches[0], dest / dest_name)
    manifest = dest / 'IMPORT_NOTES_V38.txt'
    manifest.write_text(
        'Listening Set 1 imported by V38.0.\n'
        'LISTENING_SET_1_SOURCE.docx is the authoritative Set 1 question/answer source.\n'
        'Part 2 included two supplied MP3 files, while the source document defines one conversation.\n'
        'Track 1 is assigned to the live ordering task; Track 2 is retained as an unassigned reference/alternate stimulus for admin review.\n',
        encoding='utf-8'
    )


with transaction.atomic():
    program = find_program()
    mock, section, parts = ensure_structure(program)
    archive_source_docs()

    # Create/update all supplied audio stimuli. Part 2 Track 2 is retained but deliberately unassigned.
    stimuli_by_part = {}
    for part_no in range(1, 6):
        live_tracks = [1,2,3,4] if part_no in (1,3,4,5) else [1,2]
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
            stimuli_by_part[part_no][track_no] = upsert_stimulus(
                program, part_no, track_no, transcript=transcript,
                reference=(part_no == 2 and track_no == 2),
            )

    canonical_by_part = {}
    for part_no, info in DATA.items():
        part = parts[part_no]
        if 'instructions' in names(TestPart):
            part.instructions = info['instruction']
        if 'prompt_mode' in names(TestPart): part.prompt_mode = 'audio'
        if 'question_visible' in names(TestPart): part.question_visible = True
        if 'is_active' in names(TestPart): part.is_active = True
        part.save()

        canonical = []
        for spec in info['questions']:
            canonical.append(apply_question(program, part, part_no, spec, stimuli_by_part[part_no]))
        canonical_by_part[part_no] = canonical

    # Replace only Set 1 placements in the Listening PRACTICE structure. Other Sets and Full Mocks stay untouched.
    for part_no, part in parts.items():
        old = PartQuestion.objects.filter(part=part, question__title__regex=rf'^Listening S1 P{part_no} Q\d+$')
        old.delete()
        for q in canonical_by_part[part_no]:
            m = re.search(r' Q(\d+)$', q.title)
            q_no = int(m.group(1))
            PartQuestion.objects.create(part=part, question=q, order=1000 + q_no, is_required=True)
        if 'question_count' in names(TestPart):
            # The shared Part contains many Sets, so keep this unset rather than pretending it equals one Set size.
            part.question_count = None
            part.save(update_fields=['question_count'])

    # Archive any obsolete standardized Set 1 questions that are not part of this source set.
    expected_titles = {q.title for rows in canonical_by_part.values() for q in rows}
    obsolete = Question.objects.filter(program=program, skill='listening', title__startswith='Listening S1 P').exclude(title__in=expected_titles)
    obsolete_count = 0
    for q in obsolete:
        if 'is_active' in names(Question) and q.is_active:
            q.is_active = False; q.save(update_fields=['is_active']); obsolete_count += 1

print('LISTENING SET 1 IMPORT V38.0 COMPLETE')
print('Program:', program)
print('Practice mock:', mock)
for p in range(1,6):
    rows = canonical_by_part[p]
    audio = len({q.stimulus_id for q in rows if q.stimulus_id})
    print(f'Part {p}: {len(rows)} questions, {audio} student-assigned audio track(s)')
print('Part 2 Track 2: retained as reference/alternate stimulus; not assigned to student question.')
print('Obsolete standardized Set 1 questions archived:', obsolete_count)
print('Source documents:', Path(settings.MEDIA_ROOT) / 'question_bank/source_documents/listening/set_1')

