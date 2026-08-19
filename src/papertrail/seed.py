"""The memory file every visitor starts from."""

from __future__ import annotations

from papertrail.models import Memory

HOLDER = "Arjun"

SEED: tuple[Memory, ...] = (
    Memory(
        path="diet.style",
        value="Vegetarian. No egg either.",
        note="what I eat and what I don't",
    ),
    Memory(
        path="kitchen.equipment",
        value="A kettle and a microwave in a hostel room. No stove, no hob, no oven.",
        note="what I can actually cook with",
    ),
    Memory(
        path="health.condition",
        value="Lactose intolerant, diagnosed 2023.",
        note="a diagnosed medical condition",
        sensitive=True,
    ),
    Memory(
        path="budget.weekly",
        value="\u20b91,200 a week, and that is everything after the mess bill.",
        note="how much I have to spend in a week",
        attested=True,
    ),
    Memory(
        path="location.city",
        value="Bengaluru, Koramangala.",
        note="where I live",
    ),
    Memory(
        path="schedule.evenings",
        value="Labs run until 6:30pm on weekdays. Saturdays are free after noon.",
        note="when I am free in the evenings",
    ),
    Memory(
        path="work.stack",
        value="Python and Go. Learning Rust this semester, badly.",
        note="what I build software with",
    ),
    Memory(
        path="style.tone",
        value="Terse. No preamble, no cheerleading, no bullet point that says 'in conclusion'.",
        note="how I like being spoken to",
    ),
    Memory(
        path="taste.music",
        value="Carnatic fusion. Lo-fi while studying, nothing with lyrics.",
        note="what I listen to",
    ),
    Memory(
        path="travel.commute",
        value="Cycle. Twenty minutes to campus, and I refuse to drive in this city.",
        note="how I get around",
    ),
)

STARTERS: tuple[str, ...] = (
    "What should I cook tonight?",
    "Plan my Saturday.",
    "I've started going to the gym on Tuesdays and Thursdays.",
)
