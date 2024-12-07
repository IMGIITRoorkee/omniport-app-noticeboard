from datetime import date


today = date.today()
def is_graduate(person):
    """
    Check if a student has graduated from the institution
    """
    
    try:
        if person.student.end_date is not None and person.student.end_date < today:
            return True
    except:
        return False
