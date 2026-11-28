"""Plain-language feedback shared by learning and final checks."""
COPY_VERSION = '2026.11.28.2'

def employee_text(value):
    return str(value)

def employee_feedback(message, lesson, values):
    return str(message).replace('Check the item, location and quantities.', 'Check the account, amount and reference against the practice documents.')
