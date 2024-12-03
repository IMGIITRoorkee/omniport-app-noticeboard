from datetime import date


today = date.today()
def is_passed(person):
    """
    Check if a student has graduated from the institution
    """
    
    if person.student is not None and person.student.end_date is not None and person.student.end_date < today:
        return True
    return False