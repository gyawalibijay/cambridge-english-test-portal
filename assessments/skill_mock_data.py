"""Original, unofficial B1-level starter material. Not Cambridge exam content."""

SKILLS = ("reading", "listening", "speaking", "writing")
SLUGS = {skill: f"cambridge-{skill}-skill-mock" for skill in SKILLS}
MINUTES = {"reading": 15, "listening": 15, "speaking": 12, "writing": 30}

# One finite test per skill. Parts are internal, never a list of numbered sets.
READING = (
    ("Short messages", (
        {"text": "Library notice: From Monday, the upstairs study room closes at 6 pm. You can still return books at the downstairs desk until 8 pm.",
         "prompt": "What can students do after 6 pm?", "options": ("Study upstairs", "Return books downstairs", "Borrow a study room"), "correct": 1},
        {"text": "Hi Mira, I cannot meet you outside the cinema at five. My bus is delayed. Please collect our tickets and I will join you inside before the film starts at half past five. — Anil",
         "prompt": "What does Anil ask Mira to do?", "options": ("Wait at the bus stop", "Change the film time", "Collect the tickets"), "correct": 2},
    )),
    ("Reading for detail", (
        {"text": "Rina used to drive to her office. Last month she joined a cycling group. The journey now takes ten minutes longer, but she enjoys talking to the other riders. On rainy days, she takes the bus because there is no safe place to dry her cycling clothes at work.",
         "prompt": "Why does Rina enjoy cycling to work?", "options": ("It is quicker than driving", "She can talk to other riders", "She does not have a bus stop nearby"), "correct": 1},
        {"text": "A local cafe runs a language exchange every Thursday evening. Visitors do not need to book, but they should arrive before seven to find a partner. Food is not included. Buying a drink helps the cafe pay for the room.",
         "prompt": "What should someone attending the language exchange do?", "options": ("Book a table a week before", "Bring food for a partner", "Arrive before seven"), "correct": 2},
    )),
    ("Complete the sentence", (
        {"text": "Complete the sentence with one word.", "prompt": "We arrived early ___ that we could find a good seat.", "answer": "so"},
        {"text": "Complete the sentence with one word.", "prompt": "I have lived in this town ___ three years.", "answer": "for"},
    )),
)

LISTENING = (
    {"title": "Travel announcement", "transcript": "Attention passengers. The bus to Lakeside will now leave from stand four, not stand two. The departure time is still ten thirty. Please have your tickets ready before boarding.",
     "prompt": "Which stand will the bus leave from?", "options": ("Stand two", "Stand four", "Stand ten"), "correct": 1},
    {"title": "A phone message", "transcript": "Hi Sam, it is Leena. I have booked a table for lunch on Saturday. The restaurant was full at twelve, so our reservation is at one fifteen. I will meet you at the entrance ten minutes earlier.",
     "prompt": "What time is the restaurant reservation?", "options": ("Twelve o'clock", "One oh five", "One fifteen"), "correct": 2},
    {"title": "A class update", "transcript": "This is a message for the evening photography class. Our teacher is ill today, so the lesson has moved from Tuesday to Thursday. Please bring the pictures you took at the weekend. You will not need your camera in class.",
     "prompt": "What should students bring to the next lesson?", "options": ("Their weekend pictures", "A new camera", "A doctor's note"), "correct": 0},
    {"title": "Making a plan", "transcript": "We wanted to walk in the hills this Sunday, but the forecast says it will rain all day. The museum has a new exhibition about local history. Let us go there instead, and save the walk for next weekend.",
     "prompt": "Why are the friends changing their plan?", "options": ("The museum is closing soon", "Bad weather is expected", "The hills are too far away"), "correct": 1},
    {"title": "A workplace message", "transcript": "Hello everyone. The new office computers will arrive tomorrow morning. Please save your work to the shared drive before you leave today. You can keep using your current computers until the technician asks you to stop.",
     "prompt": "What should staff do before leaving today?", "options": ("Turn off the shared drive", "Take their computers home", "Save their work to the shared drive"), "correct": 2},
)

SPEAKING = (
    ("Getting to know you", (
        "Tell us about the place where you live. What do you like about it, and why?",
        "What do you usually do in your free time? Explain why you enjoy it.",
        "Tell us about a person you enjoy spending time with. What do you do together?",
    ), "recorded_response", 5, 30),
    ("An everyday experience", (
        "Describe a useful skill you learned recently. How did you learn it, and when do you use it?",
        "Tell us about a journey you remember. Where did you go and what made it interesting?",
        "Describe a time when you helped someone. What did you do, and how did you feel afterwards?",
    ), "recorded_response", 10, 45),
    ("Read aloud", (
        "Our community library is open every afternoon. Visitors can borrow books, use a computer, or join a conversation group.",
        "The school is organising a visit to the science museum. Students should bring lunch and arrive at the main gate before nine.",
        "Learning a language takes regular practice. A short conversation every day can help you become a more confident speaker.",
    ), "read_aloud", 5, 30),
    ("Read aloud", (
        "Travelling by bus can be a good way to explore a new city. You can see different neighbourhoods and learn how local people live.",
        "A balanced routine includes time for work, rest, and exercise. Small changes to your daily habits can make a real difference.",
        "Before you buy something online, compare the prices and read the delivery information. Keep a copy of your order confirmation.",
    ), "read_aloud", 5, 30),
    ("Give your opinion", (
        "Some people prefer to study alone, while others learn better in a group. Which do you prefer? Give reasons and an example from your own experience.",
    ), "recorded_response", 30, 90),
)

WRITING = (
    ("Write an email", "Your friend Alex is visiting your town next weekend. Write an email suggesting a place to visit, explaining how to get there, and saying what Alex should bring.", 50, 120),
    ("Write a short article", "Your class website wants an article about a healthy habit. Describe a habit you find useful, explain why it helps you, and give advice to someone who wants to try it.", 80, 160),
)
