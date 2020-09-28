import swapper

from formula_one.enums.active_status import ActiveStatus

FacultyMember = swapper.load_model('kernel', 'FacultyMember')
Student = swapper.load_model('kernel', 'Student')

def get_recipients(role):
    """
    Return the recipients of all the persons of a given role
    :param role: can be all, student or faculty
    :return: the recipients of the given role
    """

    if role == 'student':
        students = Student.objects_filter(
            active_status=ActiveStatus.IS_ACTIVE,
        ) \
            .values_list('person__id', flat=True)
        return list(students)

    elif role == 'faculty':
        faculties = FacultyMember.objects_filter(
            active_status=ActiveStatus.IS_ACTIVE,
        ) \
            .values_list('person__id', flat=True)
        return list(faculties)

    elif role == 'all':
        students = Student.objects_filter(
            active_status=ActiveStatus.IS_ACTIVE,
        ) \
            .values_list('person__id', flat=True)
        faculties = FacultyMember.objects_filter(
            active_status=ActiveStatus.IS_ACTIVE,
        ) \
            .values_list('person__id', flat=True)
        return list(students.union(faculties))

    return list()
