"""Tous les textes du bot — i18n-ready (strings EN par défaut)."""

CONSENT_PROMPT = (
    "👋 Hey <b>{name}</b>!\n\n"
    "<b>{initiator}</b> is organizing a group outing and needs your input.\n\n"
    "I'll ask you 3 quick questions privately — your answers won't be visible to others.\n\n"
    "Ready to help pick the best option?"
)

BUDGET_QUESTION = (
    "💶 <b>What's your budget per person?</b>\n\n"
    "Examples: <i>20-50</i>, <i>under 40</i>, <i>any</i>\n"
    "(amounts in €)"
)

AVAILABILITY_QUESTION = (
    "📅 <b>Which dates/times work for you?</b>\n\n"
    "Be as specific or broad as you like:\n"
    "<i>this saturday evening</i>, <i>weekends only</i>, <i>fri or sat next 2 weeks</i>"
)

PREFERENCES_QUESTION = (
    "🎯 <b>Any preferences or hard nos?</b>\n\n"
    "Examples: <i>prefer rooftop bar</i>, <i>no sushi</i>, <i>need wheelchair access</i>\n\n"
    "Or just type <i>no preference</i>"
)

CONFIRM_SUMMARY = (
    "✅ <b>Here's what I've got:</b>\n\n"
    "💶 Budget: {budget}\n"
    "📅 Availability: {availability}\n"
    "🎯 Preferences: {preferences}\n\n"
    "Submit this?"
)

PREFERENCES_SUBMITTED = (
    "Done! I'll notify you as soon as the group plan is ready. 🎉"
)

PREFERENCES_DECLINED = (
    "No problem! I've noted you won't be joining this time. "
    "You'll still be notified of the final plan."
)

RATING_PROMPT = (
    "⭐ How was <b>{event_title}</b>?\n\n"
    "Your rating helps improve future suggestions for your group."
)

RATING_THANKS = "Thanks for the feedback! It'll improve the next proposal. 🙏"

GROUP_INVOKED = (
    "Got it! 🚀\n\n"
    "I'll DM everyone to collect preferences privately. "
    "You'll get the proposal in this chat once I have enough responses."
)
