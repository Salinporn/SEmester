from user import *
from fastapi import FastAPI, Request, Form, Depends, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi_login import LoginManager
from fastapi.security import OAuth2PasswordRequestForm
import ZODB, ZODB.FileStorage
import transaction
import BTrees._OOBTree
import random
import string
from datetime import datetime, timedelta
import os

class NotAuthenticatedException(Exception):
    pass

SECRET = 'xxx'

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

manager = LoginManager(SECRET, token_url='/login', use_cookie=True, custom_exception=NotAuthenticatedException)
manager.cookie_name = "session"

storage = ZODB.FileStorage.FileStorage('data/userData.fs')
db = ZODB.DB(storage)
connection = db.open()
root = connection.root

#create root if it does not exist
if not hasattr(root, "students"):
    root.students = BTrees.OOBTree.BTree()
if not hasattr(root, "teachers"):
    root.teachers = BTrees.OOBTree.BTree()
if not hasattr(root, "teacherCourses"):
    root.teacherCourses = BTrees.OOBTree.BTree()
if not hasattr(root, "studentCourses"):
    root.studentCourses = BTrees.OOBTree.BTree()
if not hasattr(root, "announcements"):
    root.announcements = BTrees.OOBTree.BTree()
if not hasattr(root, "assignments"):
    root.assignments = BTrees.OOBTree.BTree()
if not hasattr(root, "studentAssignments"):
    root.studentAssignments = BTrees.OOBTree.BTree()
if not hasattr(root, "attendances"):
    root.attendances = BTrees.OOBTree.BTree()
if not hasattr(root, "studentAttendances"):
    root.studentAttendances = BTrees.OOBTree.BTree()
  
  
#load user
@manager.user_loader()
def load_user(email: str):
    user = None

    for t in root.teachers:
        if email == root.teachers[t].getEmail():
            user = root.teachers[t]
    
    for s in root.students:
        if email == root.students[s].getEmail():
            user = root.students[s]

    return user

#check if the user is login
@app.exception_handler(NotAuthenticatedException)
def auth_exception_handler(request: Request, exc: NotAuthenticatedException):
    return RedirectResponse(url='/login')

#redirect to the correct home page (teacher or student)
@app.get("/", response_class=HTMLResponse)
async def redirect(request: Request, user_info=Depends(manager)):
    if isinstance(user_info, Student):
        return RedirectResponse(url="/home_student", status_code=302)
    elif isinstance(user_info, Teacher):
        return RedirectResponse(url="/home_teacher", status_code=302)
 
#login
@app.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login", response_class=HTMLResponse)
async def login_info(form_data: OAuth2PasswordRequestForm = Depends()):
    email = form_data.username
    password = form_data.password
    error_message = ""
    
    # Check if email is valid
    if "@" not in email:
        error_message += "\t~Please enter a valid email\n"
    if not email.endswith("@kmitl.ac.th"):
        error_message += "\t~Email must be a KMITL email\n"
    if error_message != "":
        error_message = error_message.replace('\n', '\\n')
        return f"<script> alert(\"{error_message}\"); window.history.back(); </script>"
        
    user = load_user(email)
    
    if not user:
        return f"<script> alert(\"User does not exist\"); window.history.back(); </script>"
    elif password != user.getPassword():
        return f"<script> alert(\"Incorrect password\"); window.history.back(); </script>"
    
    access_token = manager.create_access_token(data={'sub': email}, expires=timedelta(days=7))
    
    if user in root.teachers.values():
        response = RedirectResponse(url="/home_teacher", status_code=302)
    else:
        response = RedirectResponse(url="/home_student", status_code=302)
        
    manager.set_cookie(response, access_token)
    return response

#student home page
@app.get("/home_student", response_class=HTMLResponse)
async def student_home(request: Request, user=Depends(manager)):
    courses = {}
    userCourses = user.getEnrolls()  
    for c in userCourses:
        course = {}
        course["name"] = c.getName()
        course["id"] = c.getId()
        course["section"] = c.getSection()
        courses[c.getCode()] = course
    return templates.TemplateResponse("home_student.html", {"request": request, "email": user.getEmail(), "courseDict": courses})

@app.post("/home_student", response_class=HTMLResponse)
async def student_home_course(user=Depends(manager), course_code: str = Form(None)):
    
    # Check if any fields are empty
    if any(param is None for param in [course_code]):
        return f"<script> alert(\"Please fill out all fields\"); window.history.back(); </script>"
    
    # Check if code is valid
    if len(course_code) != 9:
        return f"<script> alert(\"Invalid code\"); window.history.back(); </script>"
    
    # Check if code exists
    if course_code not in root.teacherCourses:
        return f"<script> alert(\"Course does not exist\"); window.history.back(); </script>"
    
    # Check if student is already enrolled
    if user.getCourse(course_code) in user.getEnrolls():
        return f"<script> alert(\"You are already enrolled in this course\"); window.history.back(); </script>"
    else:
        root.studentCourses[course_code] = StudentCourse(root.teacherCourses[course_code].getName(), root.teacherCourses[course_code].getId(), root.teacherCourses[course_code].getSection(), root.teacherCourses[course_code].getCode(), root.teacherCourses[course_code].getCredit(), root.teacherCourses[course_code].getTeacher())
        user.addEnrolls(root.studentCourses[course_code])
        root.teacherCourses[course_code].addStudent(user)
        transaction.commit()
        return RedirectResponse(url="/home_student",status_code=302)
    
#unenroll the student user from a course
@app.post("/api/unenroll_home_student")
async def unenrolled_home_student(request: dict, user=Depends(manager)):
    course_id = request.get('courseID')
    course_sec = request.get('section')
    course = user.getCoursefromid(int(course_id), int(course_sec))
    user.removeEnrolls(course)
    for c in root.teacherCourses:
        if root.teacherCourses[c].getId() == int(course_id) and root.teacherCourses[c].getSection() == int(course_sec):
            root.teacherCourses[c].removeStudent(user)
    for s in root.studentCourses:
        if root.studentCourses[s].getId() == int(course_id) and root.studentCourses[s].getSection() == int(course_sec):
            del root.studentCourses[s]
    transaction.commit()
   
#teacher home page 
@app.get("/home_teacher", response_class=HTMLResponse)
async def teacher_home(request: Request, user=Depends(manager)):
    courses = {}
    userCourses = user.getTeaches() 
    for c in userCourses:
        course = {}
        course["name"] = c.getName()
        course["id"] = c.getId()
        course["section"] = c.getSection()
        courses[c.getCode()] = course
    return templates.TemplateResponse("home_teacher.html", {"request": request, "email": user.getEmail(), "courseDict": courses})

@app.post("/home_teacher", response_class=HTMLResponse)
async def teacher_home_course(user=Depends(manager), course_name: str = Form(None), course_id: str = Form(None), course_section: str = Form(None), course_credit: str = Form(None)):
    error_message = ""
    
    # Check if any fields are empty
    if any(param is None for param in [course_name, course_id, course_section, course_credit]):
        return f"<script> alert(\"Please fill out all fields\"); window.history.back(); </script>"
    
    # Check if ID is valid
    if len(course_id) != 8:
        error_message += "\t~Course ID must be 8 digits long\n"
    if not course_id.isdigit():
        error_message += "\t~Course ID must be a number\n"

    # Check if credit is valid
    if not course_credit.isdigit():
        error_message += "\t~Credit must be a number\n"
    
    # Check if section is valid    
    if not course_section.isdigit():
        error_message += "\t~Section must be a number\n"
        
    # Check if any errors were found and alert user
    if error_message != "":
        error_message = error_message.replace('\n', '\\n')
        return f"<script> alert(\"{error_message}\"); window.history.back(); </script>"

    if user.getCourse(int(course_id), int(course_section)) in user.getTeaches():
        return f"<script> alert(\"Course already exist\"); window.history.back(); </script>"
    else:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k = 9))
        while code in root.teacherCourses:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k = 9))
        root.teacherCourses[code] = TeacherCourse(course_name, int(course_id), int(course_section), code, int(course_credit), user.getFirstName() + " " + user.getLastName())
        user.addTeaches(root.teacherCourses[code])
        transaction.commit()
        return RedirectResponse(url="/home_teacher",status_code=302)
   
# page to choose whether to register as a student or teacher 
@app.get("/register", response_class=HTMLResponse)
async def register(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

#student register page
@app.get("/reg_student", response_class=HTMLResponse)
async def reg_student(request: Request):
    return templates.TemplateResponse("reg_student.html", {"request": request})

@app.post("/reg_student", response_class=HTMLResponse)
async def student_info(id: str = Form(None), first_name: str = Form(None), last_name: str = Form(None), email: str = Form(None), password: str = Form(None), confirm_password: str = Form(None)):
    error_message = ""
    password_error = "Problem with password:\n"
    id_error = "Problem with ID:\n"
    email_error = "Problem with email:\n"
    
    # Check if any fields are empty
    if any(param is None for param in [id, first_name, last_name, email, password, confirm_password]):
        return f"<script> alert(\"Please fill out all fields\"); window.history.back(); </script>"
    
    # Check if ID is valid
    if len(id) != 8:
        id_error += "\t~ID must be 8 digits long\n"
    if not id.isdigit():
        id_error += "\t~ID must be a number\n"
    
    # Check if email is valid  
    if "@" not in email:
        email_error += "\tPlease enter a valid email\n"
    if not email.endswith("@kmitl.ac.th"):
        email_error += "\t~Email must be a KMITL email\n"

    # Check if password is valid
    if password != confirm_password:
        password_error += "\t~Passwords do not match\n"
    if len(password) < 8:
        password_error += "\t~Password must be at least 8 characters long\n"
    if not any(char.isdigit() for char in password):
        password_error += "\t~Password must contain at least one number\n"
    if not any(char.isupper() for char in password):
        password_error += "\t~Password must contain at least one uppercase letter\n"
    if not any(char.islower() for char in password):
        password_error += "\t~Password must contain at least one lowercase letter\n"
    if not any(char in "!@#$%^&*()-_=+[]{}\\|;:'\",.<>/?`~" for char in password):
        password_error += "\t~Password must contain at least one special character\n"
    
    # Check if any errors were found and alert user
    if id_error != "Problem with ID:\n":
        error_message += id_error
    if email_error != "Problem with email:\n":
        error_message += email_error
    if password_error != "Problem with password:\n":
        error_message += password_error
    if error_message != "":
        error_message = error_message.replace('\n', '\\n')
        return f"<script> alert(\"{error_message}\"); window.history.back(); </script>"
    else:
        # Check if ID is already used
        if int(id) in root.students:
            return f"<script> alert(\"Student already exist\"); window.history.back(); </script>"
        else:
            # Add student to database
            root.students[int(id)] = Student(first_name, last_name, int(id), email, password)
            transaction.commit()
            return RedirectResponse(url="/login",status_code=302)
 
#teacher register page       
@app.get("/reg_teacher", response_class=HTMLResponse)
async def reg_teacher(request: Request):
    return templates.TemplateResponse("reg_teacher.html", {"request": request})

@app.post("/reg_teacher", response_class=HTMLResponse)
async def teacher_info(first_name: str = Form(None), last_name: str = Form(None), email: str = Form(None), password: str = Form(None), confirm_password: str = Form(None)):
    error_message = ""
    password_error = "Problem with password:\n"
    email_error = "Problem with email:\n"
    
    # Check if any fields are empty
    if any(param is None for param in [first_name, last_name, email, password, confirm_password]):
        return f"<script> alert(\"Please fill out all fields\"); window.history.back(); </script>"
    
    # Check if email is valid  
    if "@" not in email:
        email_error += "\tPlease enter a valid email\n"
    if not email.endswith("@kmitl.ac.th"):
        email_error += "\t~Email must be a KMITL email\n"

    # Check if password is valid
    if password != confirm_password:
        password_error += "\t~Passwords do not match\n"
    if len(password) < 8:
        password_error += "\t~Password must be at least 8 characters long\n"
    if not any(char.isdigit() for char in password):
        password_error += "\t~Password must contain at least one number\n"
    if not any(char.isupper() for char in password):
        password_error += "\t~Password must contain at least one uppercase letter\n"
    if not any(char.islower() for char in password):
        password_error += "\t~Password must contain at least one lowercase letter\n"
    if not any(char in "!@#$%^&*()-_=+[]{}\\|;:'\",.<>/?`~" for char in password):
        password_error += "\t~Password must contain at least one special character\n"
    
    # Check if any errors were found and alert user
    if email_error != "Problem with email:\n":
        error_message += email_error
    if password_error != "Problem with password:\n":
        error_message += password_error
    if error_message != "":
        error_message = error_message.replace('\n', '\\n')
        return f"<script> alert(\"{error_message}\"); window.history.back(); </script>"
    else:
        # Check if email is already used
        if email in root.teachers:
            return f"<script> alert(\"Teacher already exist\"); window.history.back(); </script>"
        else:
            # Add teacher to database
            root.teachers[email] = Teacher(first_name, last_name, email, password)
            transaction.commit()
            return RedirectResponse(url="/login",status_code=302)

#course details
@app.get("/Teacher/Course/{course_id}/{course_sec}", response_class=HTMLResponse)
async def teacher_course(request: Request, course_id: str = None, course_sec: str = None, user=Depends(manager)):
    course = user.getCourse(int(course_id), int(course_sec))
    return templates.TemplateResponse("teacher_course.html", {"request": request, "email": user.getEmail(),"course_name": course.getName(), "course_id": course_id, "course_sec": course_sec, "course_code": course.getCode(), "course_credit": course.getCredit(), "course_teacher": course.getTeacher(), "gradeScheme": course.getGradeScheme()})

@app.post("/Teacher/Course/{course_id}/{course_sec}", response_class=HTMLResponse)
async def set_grade_scheme(user=Depends(manager), course_id: str = None, course_sec: str = None, minA: str = Form(None), minBplus: str = Form(None), minB: str = Form(None), minCplus: str = Form(None), minC: str = Form(None), minDplus: str = Form(None), minD: str = Form(None), minF: str = Form(None), maxA: str = Form(None), maxBplus: str = Form(None), maxB: str = Form(None), maxCplus: str = Form(None), maxC: str = Form(None), maxDplus: str = Form(None), maxD: str = Form(None), maxF: str = Form(None)):
    
    if any(param is None for param in [minA, minBplus, minB, minCplus, minC, minDplus, minD, minF, maxA, maxBplus, maxB, maxCplus, maxC, maxDplus, maxD, maxF]):
        return f"<script> alert(\"Please fill out all fields\"); window.history.back(); </script>"
    
    course = user.getCourse(int(course_id), int(course_sec))
    gradeScheme = {}
    gradeScheme["A"] = [int(minA), int(maxA)]
    gradeScheme["B+"] = [int(minBplus), int(maxBplus)]
    gradeScheme["B"] = [int(minB), int(maxB)]
    gradeScheme["C+"] = [int(minCplus), int(maxCplus)]
    gradeScheme["C"] = [int(minC), int(maxC)]
    gradeScheme["D+"] = [int(minDplus), int(maxDplus)]
    gradeScheme["D"] = [int(minD), int(maxD)]
    gradeScheme["F"] = [int(minF), int(maxF)]
    course.setGradeScheme(gradeScheme)
    for s in course.getStudents():
        s.getCoursefromid(int(course_id), int(course_sec)).setGradeScheme(gradeScheme)
    transaction.commit()
    return RedirectResponse(url="/Teacher/Course/" + course_id + "/" + course_sec, status_code=302)

@app.get("/Student/Course/{course_id}/{course_sec}", response_class=HTMLResponse)
async def student_course(request: Request, course_id: str = None, course_sec: str = None, user=Depends(manager)):
    course = user.getCoursefromid(int(course_id), int(course_sec))
    return templates.TemplateResponse("student_course.html", {"request": request, "email": user.getEmail(),"course_name": course.getName(), "course_id": course_id, "course_sec": course_sec, "course_code": course.getCode(), "course_credit": course.getCredit(), "course_teacher": course.getTeacher()})

#announcement page for students to check announcement
@app.get("/Student/Announcement/{course_id}/{course_sec}", response_class=HTMLResponse)
async def student_announcement(request: Request, course_id: str = None, course_sec: str = None, user=Depends(manager)):
    course = user.getCoursefromid(int(course_id), int(course_sec))
    announcements = {}
    for a in course.getAnnouncements():
        announcement = {}
        announcement["content"] = a.getContent()
        announcement["date"] = a.getDate()
        announcement["filename"] = a.getFilename()
        announcements[a.getTopic()] = announcement
    return templates.TemplateResponse("annoucement_student.html", {"request": request, "email": user.getEmail(), "course_id": course_id, "course_sec": course_sec, "announcement": announcements, "course_name": course.getName()})

# page for teacher to make announcement
@app.get("/Teacher/Announcement/{course_id}/{course_sec}", response_class=HTMLResponse)
async def teacher_announcement(request: Request, course_id: str = None, course_sec: str = None, user=Depends(manager)):
    course = user.getCourse(int(course_id), int(course_sec))
    announcements = {}
    for a in user.getCourse(int(course_id), int(course_sec)).getAnnouncements():
        announcement = {}
        announcement["content"] = a.getContent()
        announcement["date"] = a.getDate()
        announcement["filename"] = a.getFilename()
        announcements[a.getTopic()] = announcement
    return templates.TemplateResponse("announcement_teacher.html", {"request": request, "email": user.getEmail(), "course_id": course_id, "course_sec": course_sec, "announcement": announcements, "course_name": course.getName()})

@app.post("/Teacher/Announcement/{course_id}/{course_sec}", response_class=HTMLResponse)
async def teacher_announcement_info(user=Depends(manager), course_id: str = None, course_sec: str = None, topic: str = Form(None), content: str = Form(None), files: list[UploadFile] = File(None)):

    #Check if any fields are empty
    if any(param is None for param in [topic, content]):
        return f"<script> alert(\"Please fill out all fields\"); window.history.back(); </script>"
    
    filename = []
    for file in files:
        if file.filename:
            if not os.path.exists("static/announcement/uploaded/" + course_id + "/" + course_sec):
                os.makedirs("static/announcement/uploaded/" + course_id + "/" + course_sec)
            filename.append(file.filename)
            filedata = file.file.read()
            with open("static/announcement/uploaded/" + course_id + "/" + course_sec + "/" + file.filename, "wb") as f:
                f.write(filedata)

    for a in user.getCourse(int(course_id), int(course_sec)).getAnnouncements():
        if topic == a.getTopic():
            return f"<script> alert(\"Announcement already exist\"); window.history.back(); </script>"
    
    date = datetime.now()
    year = date.year
    month = date.month
    day = date.day
    hour = date.hour
    minute = date.minute
    second = date.second
    current_date = str(day) + "/" + str(month) + "/" + str(year) + " " + str(hour) + ":" + str(minute) + ":" + str(second)
    root.announcements[topic] = Announcement(topic, content, current_date, filename)
    user.getCourse(int(course_id), int(course_sec)).addAnnouncement(root.announcements[topic])
    for s in user.getCourse(int(course_id), int(course_sec)).getStudents():
        s.getCoursefromid(int(course_id), int(course_sec)).addAnnouncement(root.announcements[topic])
    transaction.commit()
    redirect = "/Teacher/Announcement/" + course_id + "/" + course_sec
    return RedirectResponse(url=redirect,status_code=302)

#delete announcement
@app.post("/api/delete-announcement/{course_id}/{course_sec}")
async def delete_announcement(request: dict, user=Depends(manager), course_id: str = None, course_sec: str = None):
    course = user.getCourse(int(course_id), int(course_sec))
    topic_to_delete = request.get('topic')
    if topic_to_delete:
        if root.announcements.get(topic_to_delete):
            course.removeAnnouncement(root.announcements[topic_to_delete])
            for s in course.getStudents():
                s.getCoursefromid(int(course_id), int(course_sec)).removeAnnouncement(root.announcements[topic_to_delete])
            file = root.announcements[topic_to_delete].getFilename()
            if file:
                for f in file:
                    os.remove("static/announcement/uploaded/" + course_id + "/" + course_sec + "/" + f)
            del root.announcements[topic_to_delete]
            transaction.commit()

#list of dates of class for teacher to check attendance
@app.get("/Teacher/Attendance/{course_id}/{course_sec}", response_class=HTMLResponse)
async def teacher_attendace_dates(request: Request, course_id: str = None, course_sec: str = None, user=Depends(manager)):
    course = user.getCourse(int(course_id), int(course_sec))
    attendance = course.getAttendances()
    attendanceDates = {}
    for attendance_date in attendance:
        attendanceDates[attendance_date.getDate()] = attendance_date.getDate()
    return templates.TemplateResponse("attendance_dates_teacher.html", {"request": request, "email": user.getEmail(), "course_id": course_id, "course_sec": course_sec, "attendanceDate": attendanceDates, "course_name": course.getName()})

@app.post("/Teacher/Attendance/{course_id}/{course_sec}", response_class=HTMLResponse)
async def teacher_attendance_dates_info(teacher=Depends(manager), course_id: str = None, course_sec: str = None, date: str = Form(None)):
    formatted_date = datetime.strptime(date, "%Y-%m-%d").strftime("%d/%m/%Y") 
    course = teacher.getCourse(int(course_id), int(course_sec))
    attendances = course.getAttendances()
    for d in attendances:
        if d.getDate() == formatted_date:
            return f"<script> alert(\"Attendance date already exist\"); window.history.back(); </script>"
    
    root.attendances[formatted_date] = Attendance(formatted_date) 
    course.addAttendance(root.attendances[formatted_date])

    for student in course.getStudents():
        studentCourse = student.getCoursefromid(int(course_id), int(course_sec))
        root.studentAttendances[formatted_date] = StudentAttendance(formatted_date)
        studentCourse.addAttendance(root.studentAttendances[formatted_date])
    transaction.commit()

    redirect = f"/Teacher/Attendance/{course_id}/{course_sec}"
    return RedirectResponse(url=redirect, status_code=302)

#delete attendance datte
@app.post("/api/delete-attendanceDate/{course_id}/{course_sec}")
async def delete_attendanceDate(request: dict, user=Depends(manager), course_id: str = None, course_sec: str = None):
    course = user.getCourse(int(course_id), int(course_sec))
    date_to_delete = request.get('date')
    if date_to_delete:
        if root.attendances.get(date_to_delete):
            course.removeAttendance(root.attendances[date_to_delete])
            for s in course.getStudents():
                s.getCoursefromid(int(course_id), int(course_sec)).removeAttendance(root.studentAttendances[date_to_delete])
            del root.studentAttendances[date_to_delete]
            del root.attendances[date_to_delete]
            transaction.commit()

#page for teacher to check attendance
@app.get("/Teacher/Attendance/{course_id}/{course_sec}/{date}", response_class=HTMLResponse)
async def teacher_attendance(request: Request, course_id: str = None, course_sec: str = None, user=Depends(manager), date: str = None):
    course = user.getCourse(int(course_id), int(course_sec))
    attendances = {}
    date_parts = date.split("-")
    formatted_date = date_parts[0] + "/" + date_parts[1] + "/" + date_parts[2]
    for s in course.getStudents():
        attendance = s.getCoursefromid(int(course_id), int(course_sec)).getAttendance(formatted_date)
        student = {}
        student["name"] = s.getFirstName() + " " + s.getLastName()
        student["status"] = attendance.getStatus()
        student["remark"] = attendance.getRemark()
        attendances[s.getId()] = student
    return templates.TemplateResponse("attendance_teacher.html", {"request": request, "email": user.getEmail(), "course_id": course_id, "course_sec": course_sec, "course_name": course.getName(), "attendanceDict": attendances, "totalPresent": course.getAttendance(formatted_date).getTotalPresent(), "totalAbsent": course.getAttendance(formatted_date).getTotalAbsent(), "totalLate": course.getAttendance(formatted_date).getTotalLate(), "date": date})

@app.post("/Teacher/Attendance/{course_id}/{course_sec}/{date}", response_class=HTMLResponse)
async def teacher_attendance_info(request: Request, user=Depends(manager), course_id: str = None, course_sec: str = None, date: str = None):
    course = user.getCourse(int(course_id), int(course_sec))
    date_parts = date.split("-")
    formatted_date = date_parts[0] + "/" + date_parts[1] + "/" + date_parts[2]
    totalPresent = 0
    totalAbsent = 0
    totalLate = 0
    
    form = await request.form()

    for s in course.getStudents():
        attendance = s.getCoursefromid(int(course_id), int(course_sec)).getAttendance(formatted_date)
        status = form.get("status_" + str(s.getId()))
        remark = form.get("remark_" + str(s.getId()))
        attendance.setStatus(status)
        attendance.setRemark(remark)
        if attendance.getStatus() == "present":
            totalPresent += 1
        elif attendance.getStatus() == "absent":
            totalAbsent += 1
        elif attendance.getStatus() == "late":
            totalLate += 1
    course.getAttendance(formatted_date).setTotalPresent(totalPresent)
    course.getAttendance(formatted_date).setTotalAbsent(totalAbsent)
    course.getAttendance(formatted_date).setTotalLate(totalLate)
    transaction.commit()
    return RedirectResponse(url="/Teacher/Attendance/" + course_id + "/" + course_sec + "/" + date, status_code=302)

#attendance overview page for student
@app.get("/attendance-overview/", response_class=HTMLResponse)
async def student_attendance_overview(request: Request, user=Depends(manager)):
    courses = {}
    userCourses = user.getEnrolls()  
    for c in userCourses:
        course = {}
        totalPresent = 0
        totalAbsent = 0
        totalLate = 0
        course["name"] = c.getName()
        course["sec"] = c.getSection()
        for a in c.getAttendances():
            if a.getStatus() == "present":
                totalPresent += 1
            elif a.getStatus() == "absent":
                totalAbsent += 1
            elif a.getStatus() == "late":
                totalLate += 1
        course["totalPresent"] = totalPresent
        course["totalAbsent"] = totalAbsent
        course["totalLate"] = totalLate
        courses[c.getId()] = course
    return templates.TemplateResponse("attendance_overview_student.html", {"request": request, "email": user.getEmail(), "attendanceDict": courses})

@app.get("/attendance-overview/{course_id}/{course_sec}", response_class=HTMLResponse)
async def student_attendance_overview_course(request: Request, user=Depends(manager), course_id: str = None, course_sec: str = None):
    course = user.getCoursefromid(int(course_id), int(course_sec))
    attendances = {}
    for a in course.getAttendances():
        attendance = {}
        attendance["date"] = a.getDate()
        attendance["status"] = a.getStatus()
        attendance["remark"] = a.getRemark()
        attendances[a.getDate()] = attendance
    return templates.TemplateResponse("attendance_student.html", {"request": request, "email": user.getEmail(), "course_id": course_id, "course_sec": course_sec, "course_name": course.getName(), "attendanceDict": attendances})

#student assignments page
@app.get("/Student/Assignment/{course_id}/{course_sec}", response_class=HTMLResponse)
async def student_assignment(request: Request, course_id: str = None, course_sec: str = None, user=Depends(manager)):
    course = user.getCoursefromid(int(course_id), int(course_sec))
    assignments = {}
    for a in course.getAssignments():
        assignment = {}
        assignment["topic"] = a.getName()
        assignment["content"] = a.getDescription()
        assignment["due_date"] = a.getDueDate()
        assignment["due_time"] = a.getDueTime()
        assignment["filename"] = a.getFilename()
        assignment["score"] = a.getMaxScore()
        if not isinstance(a, StudentAssignment):
            assignment["status"] = "Not submitted"
        else:
            assignment["status"] = a.getStatus()
        assignments[a.getCode()] = assignment
    return templates.TemplateResponse("assignment_student.html", {"request": request, "email": user.getEmail(), "course_id": course_id, "course_sec": course_sec, "course_name": course.getName(), "assignmentDict": assignments})

#info of te assignment and submission page
@app.get("/Student/Assignment/{course_id}/{course_sec}/{code}", response_class=HTMLResponse)
async def student_assignment_info(request: Request, user=Depends(manager), course_id: str = None, course_sec: str = None, code: str = None):
    course = user.getCoursefromid(int(course_id), int(course_sec))
    assignment = course.getAssignment(code)
    files = {}
    files["filename"] = assignment.getFilename()
    return templates.TemplateResponse("assignment_submission.html", {"request": request, "email": user.getEmail(), "course_id": course_id, "course_sec": course_sec, "course_name": course.getName(), "assignment_name": assignment.getName(), "description": assignment.getDescription(), "due_date": assignment.getDueDate(), "due_time": assignment.getDueTime(), "filenames": files, "assignment_score": assignment.getMaxScore(), "assignment_code": assignment.getCode()})

@app.post("/Student/Assignment/{course_id}/{course_sec}/{code}", response_class=HTMLResponse)
async def student_assignment_submission(request: Request, user=Depends(manager), course_id: str = None, course_sec: str = None, code: str = None, files: list[UploadFile] = File(None)):
    course = user.getCoursefromid(int(course_id), int(course_sec))
    assignment = course.getAssignment(code)
    filename = []
    for file in files:
        if file.filename:
            if not os.path.exists("static/assignment/uploaded/" + course_id + "/" + course_sec + "/Student"):
                os.makedirs("static/assignment/uploaded/" + course_id + "/" + course_sec + "/Student")
            filename.append(file.filename)
            filedata = file.file.read()
            with open("static/assignment/uploaded/" + course_id + "/" + course_sec + "/Student/" + file.filename, "wb") as f:
                f.write(filedata)
    
    if filename == []:
        return f"<script> alert(\"Please upload a file\"); window.history.back(); </script>"
    
    date = datetime.now()
    year = date.year
    month = date.month
    day = date.day
    hour = date.hour
    minute = date.minute
    
    formatted_date = str(day) + "/" + str(month) + "/" + str(year)
    formatted_time = str(hour) + ":" + str(minute)
    root.studentAssignments[code] = StudentAssignment(assignment.getName(), assignment.getMaxScore(), assignment.getWeight(), assignment.getDueDate(), assignment.getDueTime(), filename, assignment.getDescription(), assignment.getCode(), formatted_date, formatted_time)
    course.replaceAssignment(root.studentAssignments[code])
    transaction.commit()
    return RedirectResponse(url="/Student/Assignment/" + course_id + "/" + course_sec, status_code=302)

# info of the submitted assignment
@app.get("/Student/Assignment/Completed/{course_id}/{course_sec}/{code}", response_class=HTMLResponse)
async def completed(request: Request, user=Depends(manager), course_id: str = None, course_sec: str = None, code: str = None):
    course = user.getCoursefromid(int(course_id), int(course_sec))
    file_lastname = ["py", "java", "cpp", "c", "txt", "js", "html", "css", "r", "R", "Java", "rs"]
    assignment = root.assignments[code]
    studentAssignment = course.getAssignment(code)
    attachment = {}
    attachment["filename"] = assignment.getFilename()
    assignment_submission = {}
    assignment_submission["filename"] = studentAssignment.getFilename()
    content = {}
    for f in studentAssignment.getFilename():
        file = open("static/assignment/uploaded/" + course_id + "/" + course_sec + "/Student/" + f, "r")
        if f.split(".")[-1] in file_lastname:
            content[f] = file.read()
        else:
            content[f] = "File cannot be displayed"
    assignment_submission["content"] = content
    return templates.TemplateResponse("assignment_submission_completed.html", {"request": request, "email": user.getEmail(), "course_id": course_id, "course_sec": course_sec, "course_name": course.getName(), "assignment_name": assignment.getName(), "assignment_score": assignment.getMaxScore(), "due_date": assignment.getDueDate(), "due_time": assignment.getDueTime(), "description": assignment.getDescription(), "code": code, "submitted_filenames": assignment_submission, "filenames": attachment, "score_receive": studentAssignment.getScore(), "comment": studentAssignment.getComment(), "submitted_date": studentAssignment.getSubmitDate(), "submitted_time": studentAssignment.getSubmitTime(), "status": studentAssignment.getStatus()})

# page to assign assignments
@app.get("/Teacher/Assignment/{course_id}/{course_sec}", response_class=HTMLResponse)
async def teacher_assignment(request: Request, course_id: str = None, course_sec: str = None, user=Depends(manager)):
    course = user.getCourse(int(course_id), int(course_sec))
    assignments = {}
    for a in course.getAssignments():
        assignment = {}
        assignment["topic"] = a.getName()
        assignment["content"] = a.getDescription()
        assignment["due_date"] = a.getDueDate()
        assignment["due_time"] = a.getDueTime()
        assignment["filename"] = a.getFilename()
        assignment["score"] = a.getMaxScore()
        assignments[a.getCode()] = assignment
    return templates.TemplateResponse("assignment_teacher.html", {"request": request, "email": user.getEmail(), "course_id": course_id, "course_sec": course_sec, "course_name": course.getName(), "assignmentDict": assignments})

@app.post("/Teacher/Assignment/{course_id}/{course_sec}", response_class=HTMLResponse)
async def teacher_assign(user=Depends(manager), course_id: str = None, course_sec: str = None, topic: str = Form(None), content: str = Form(None), files: list[UploadFile] = File(None), due_date: str = Form(None), due_time: str = Form(None), score: str = Form(None), weight: str = Form(None)):
    
    #Check if any fields are empty
    if any(param is None for param in [topic, content, due_date, due_time]):
        return f"<script> alert(\"Please fill out all fields\"); window.history.back(); </script>"
    
    filename = []
    for file in files:
        if file.filename:
            if not os.path.exists("static/assignment/uploaded/" + course_id + "/" + course_sec):
                os.makedirs("static/assignment/uploaded/" + course_id + "/" + course_sec)
            filename.append(file.filename)
            filedata = file.file.read()
            with open("static/assignment/uploaded/" + course_id + "/" + course_sec + "/" + file.filename, "wb") as f:
                f.write(filedata)
    
    
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k = 4))
    course = user.getCourse(int(course_id), int(course_sec))
    while course.getAssignment(code) in course.getAssignments():
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k = 4))
        
    root.assignments[code] = Assignment(topic, score, weight, due_date, due_time, filename, content, code)
    course.addAssignment(root.assignments[code])
    for s in course.getStudents():
        s.getCoursefromid(int(course_id), int(course_sec)).addAssignment(root.assignments[code])
    transaction.commit()
    return RedirectResponse(url="/Teacher/Assignment/" + course_id + "/" + course_sec, status_code=302)

# page to check submitted asignments
@app.get("/Teacher/Assignment/{course_id}/{course_sec}/{code}", response_class=HTMLResponse)
async def display_submit(request: Request, user=Depends(manager), course_id: str = None, course_sec: str = None, code: str = None):
    course = user.getCourse(int(course_id), int(course_sec))
    assignment = course.getAssignment(code)
    students = {}
    for s in course.getStudents():
        studentCourse = s.getCoursefromid(int(course_id), int(course_sec))
        studentAssignment = studentCourse.getAssignment(code)
        student = {}
        student["name"] = s.getFirstName() + " " + s.getLastName()
        student["due_date"] = assignment.getDueDate()
        student["due_time"] = assignment.getDueTime()
        if isinstance(studentAssignment, StudentAssignment):
            student["status"] = studentAssignment.getStatus()
            student["submit_date"] = studentAssignment.getSubmitDate()
            student["submit_time"] = studentAssignment.getSubmitTime()
        else:
            student["status"] = "Not submitted"
            student["submit_date"] = ""
            student["submit_time"] = ""
        students[s.getId()] = student
    return templates.TemplateResponse("assignment_student_list.html", {"request": request, "email": user.getEmail(), "course_id": course_id, "course_sec": course_sec, "course_name": course.getName(), "assignment_name": assignment.getName(), "studentDict": students, "code": code})

@app.get("/Teacher/Assignment/{course_id}/{course_sec}/{code}/{id}", response_class=HTMLResponse)
async def display_student_submission(request: Request, user=Depends(manager), course_id: str = None, course_sec: str = None, code: str = None, id: str = None):
    course = user.getCourse(int(course_id), int(course_sec))
    file_lastname = ["py", "java", "cpp", "c", "txt", "js", "html", "css", "r", "R", "Java", "rs"]
    assignment = course.getAssignment(code)
    student = course.getStudent(int(id))
    studentCourse = student.getCoursefromid(int(course_id), int(course_sec))
    studentAssignment = studentCourse.getAssignment(code)
    attachments = {}
    attachments["filename"] = assignment.getFilename()
    files = {}
    files["filename"] = studentAssignment.getFilename()
    content = {}
    for f in studentAssignment.getFilename():
        file = open("static/assignment/uploaded/" + course_id + "/" + course_sec + "/Student/" + f, "r")
        if f.split(".")[-1] in file_lastname:
            content[f] = file.read()
        else:
            content[f] = "File cannot be displayed"
    files["content"] = content
    return templates.TemplateResponse("assignment_checker.html", {"request": request, "email": user.getEmail(), "course_id": course_id, "course_sec": course_sec, "course_name": course.getName(), "assignment_name": assignment.getName(), "student_name": student.getFirstName() + " " + student.getLastName(), "id": id, "filenames": files, "assignment_score": assignment.getMaxScore(), "score": studentAssignment.getScore(), "comment": studentAssignment.getComment(), "attachments": attachments, "submitted_file": files, "description": assignment.getDescription(), "submit_date": studentAssignment.getSubmitDate(), "submit_time": studentAssignment.getSubmitTime(), "code": code, "due_date": assignment.getDueDate(), "due_time": assignment.getDueTime()})

@app.post("/Teacher/Assignment/{course_id}/{course_sec}/{code}/{id}", response_class=HTMLResponse)
async def set_score(user=Depends(manager), course_id: str = None, course_sec: str = None, code: str = None, id: str = None, score: str = Form(None), comment: str = Form(None)):
    
    if any(param is None for param in [score]):
        return f"<script> alert(\"Please fill in the score\"); window.history.back(); </script>"
    
    course = user.getCourse(int(course_id), int(course_sec))
    student = course.getStudent(int(id))
    studentCourse = student.getCoursefromid(int(course_id), int(course_sec))
    studentAssignment = studentCourse.getAssignment(code)
    studentAssignment.setScore(int(score))
    if comment is not None:
        studentAssignment.setComment(comment)
    else:
        studentAssignment.setComment("")
    studentAssignment.setStatus("Graded")
    transaction.commit()
    return RedirectResponse(url="/Teacher/Assignment/" + course_id + "/" + course_sec + "/" + code + "/" + id, status_code=302)

#delete assignment
@app.post("/api/delete-assignment/{course_id}/{course_sec}")
async def delete_assignment(request: dict, user=Depends(manager), course_id: str = None, course_sec: str = None):
    course = user.getCourse(int(course_id), int(course_sec))
    topic_to_delete = request.get('topic')
    if topic_to_delete:
        if root.assignments.get(topic_to_delete):
            course.removeAssignment(root.assignments[topic_to_delete])
            for s in course.getStudents():
                s.getCoursefromid(int(course_id), int(course_sec)).removeAssignment(root.assignments[topic_to_delete])
            file = root.assignments[topic_to_delete].getFilename()
            if file:
                for f in file:
                    os.remove("static/assignment/uploaded/" + course_id + "/" + course_sec + "/" + f)
            if isinstance(root.assignments[topic_to_delete], StudentAssignment):
                del root.studentAssignments[topic_to_delete]
            del root.assignments[topic_to_delete]
            transaction.commit()

#unsubmit assignment    
@app.post("/api/delete-assignment-submission/{course_id}/{course_sec}/{code}")
async def delete_assignment(request: dict, user=Depends(manager), course_id: str = None, course_sec: str = None, code: str = None):
    course = user.getCoursefromid(int(course_id), int(course_sec))
    assignment = course.getAssignment(code)
    topic_to_delete = request.get('topic')
    if topic_to_delete:
        if root.assignments.get(topic_to_delete):
            course.replaceAssignment(root.assignments[topic_to_delete])
            file = assignment.getFilename()
            if file:
                for f in file:
                    os.remove("static/assignment/uploaded/" + course_id + "/" + course_sec + "/" + "Student/" + f)
            del root.studentAssignments[topic_to_delete]
            transaction.commit()

#student grade overview
@app.get("/Student/Grade", response_class=HTMLResponse)
async def student_grade_overview(request: Request, user=Depends(manager)):
    courses = {}
    grades = [0, 0, 0, 0, 0, 0, 0, 0]
    userCourses = user.getEnrolls()
    for c in userCourses:
        course = {}
        course["name"] = c.getName()
        course["sec"] = c.getSection()
        course["grade"] = c.getGrade()
        course["credit"] = c.getCredit()
        course["grade"] = c.getGrade()
        course["currentScore"] = c.getTotalScore()
        courses[c.getId()] = course
        
        if c.getGrade() == "A":
            grades[0] += 1
        elif c.getGrade() == "B+":
            grades[1] += 1
        elif c.getGrade() == "B":
            grades[2] += 1
        elif c.getGrade() == "C+":
            grades[3] += 1
        elif c.getGrade() == "C":
            grades[4] += 1
        elif c.getGrade() == "D+":
            grades[5] += 1
        elif c.getGrade() == "D":
            grades[6] += 1
        elif c.getGrade() == "F":
            grades[7] += 1
            
    return templates.TemplateResponse("grade_overview_student.html", {"request": request, "email": user.getEmail(), "courseDict": courses, "grades": grades})

#student scores for each course
@app.get("/Student/Grade/{course_id}/{course_sec}", response_class=HTMLResponse)
async def student_grade(request: Request, course_id: str = None, course_sec: str = None, user=Depends(manager)):
    course = user.getCoursefromid(int(course_id), int(course_sec))
    for t in root.teachers:
        if root.teachers[t].getFirstName() == course.getTeacher().split()[0] and root.teachers[t].getLastName() == course.getTeacher().split()[1]:
            teacher = root.teachers[t]
    teacherCourse = teacher.getCourse(int(course_id), int(course_sec))
    assignments = {}
    for a in course.getAssignments():
        assignment = {}
        assignment["topic"] = a.getName()
        assignment["weight"] = a.getWeight()
        assignment["total_score"] = a.getMaxScore()
        total_student = 0
        mean = 0
        min = int(a.getMaxScore())
        max = int(a.getMaxScore())
        for s in teacherCourse.getStudents():
            studentCourse = s.getCoursefromid(int(course_id), int(course_sec))
            studentAssignment = studentCourse.getAssignment(a.getCode())
            if isinstance(studentAssignment, StudentAssignment):
                if studentAssignment.getScore() < min:
                    min = studentAssignment.getScore()
                elif studentAssignment.getScore() > max:
                    max = studentAssignment.getScore()
                mean += studentAssignment.getScore()
                if total_student == 0:
                    min = studentAssignment.getScore()
                    max = studentAssignment.getScore()
                total_student += 1
        if total_student != 0:
            mean = mean / total_student
        assignment["mean"] = mean
        assignment["min"] = min
        assignment["max"] = max
        if isinstance(a, StudentAssignment):
            if a.getStatus() == "Graded":
                assignment["score"] = a.getScore()
            else:
                assignment["score"] = "Not graded"
        else:
            assignment["score"] = 0
        assignments[a.getCode()] = assignment
    return templates.TemplateResponse("grade_student.html", {"request": request, "email": user.getEmail(), "course_sec": course_sec,"course_id": course_id, "assignmentDict": assignments})

# for teacher to overview students' grades of each course and scores of each assignment
@app.get("/Teacher/Grade/{course_id}/{course_sec}", response_class=HTMLResponse)
async def teacher_grade_by_assignment(request: Request, course_id: str = None, course_sec: str = None, user=Depends(manager)):
    course = user.getCourse(int(course_id), int(course_sec))
    assignments = {}
    scoreRange = [0, 0, 0, 0, 0, 0]
    for a in course.getAssignments():
        assignments[a.getCode()] = a.getName()
    gradeDict = {}
    gradeScheme = course.getGradeScheme()
    min = float(course.getMin())
    max = float(course.getMax())
    for s in course.getStudents():
        studentCourse = s.getCoursefromid(int(course_id), int(course_sec))
        student = {}
        student["name"] = s.getFirstName() + " " + s.getLastName()
        grade = ""
        totalScore = studentCourse.getTotalScore()
        if gradeScheme != {}:
            for key, value in gradeScheme.items():
                if studentCourse.getGrade() == "":     
                    if value[0] <= totalScore <= value[1]:
                        studentCourse.setGrade(key)
                        transaction.commit()
        grade = studentCourse.getGrade()
        student["grade"] = grade
        student["score"] = studentCourse.getTotalScore()
        gradeDict[s.getId()] = student
        
        if 0 <= totalScore < 50:
            scoreRange[0] += 1
        elif 50 <= totalScore < 60:
            scoreRange[1] += 1
        elif 60 <= totalScore < 70:
            scoreRange[2] += 1
        elif 70 <= totalScore < 80:
            scoreRange[3] += 1
        elif 80 <= totalScore < 90:
            scoreRange[4] += 1
        elif 90 <= totalScore <= 100:
            scoreRange[5] += 1
        
    mean = course.getMean()
    standard_deviation = course.getSD()
    return templates.TemplateResponse("grade_teacher.html", {"request": request, "email": user.getEmail(), "course_id": course_id, "course_sec": course_sec, "course_name": course.getName(), "assignmentDict": assignments, "gradeScheme": gradeScheme, "gradeDict": gradeDict, "mean": mean, "min": min, "max": max, "std": standard_deviation, "score_range": scoreRange})

# for teacher to set student's grades manually
@app.post ("/Teacher/Grade/{course_id}/{course_sec}", response_class=HTMLResponse)
async def save(request: Request, user=Depends(manager), course_id: str = None, course_sec: str = None):
    course = user.getCourse(int(course_id), int(course_sec))
    
    form = await request.form()
    for s in course.getStudents():
        studentCourse = s.getCoursefromid(int(course_id), int(course_sec))
        grade = form.get("grade_" + str(s.getId()))
        studentCourse.setGrade(grade)
        if studentCourse.getGrade() == "":
            return f"<script> alert(\"Please fill in all the grades\"); window.history.back(); </script>"
    transaction.commit()
    return RedirectResponse(url="/Teacher/Grade/" + course_id + "/" + course_sec, status_code=302)

# for teacher to check scores of students in the assignment
@app.get("/Teacher/Grade/Assignment/{course_id}/{course_sec}/{code}", response_class=HTMLResponse)
async def teacher_grade_assignment(request: Request, course_id: str = None, course_sec: str = None, user=Depends(manager), code: str = None):
    course = user.getCourse(int(course_id), int(course_sec))
    assignment = course.getAssignment(code)
    students = {}
    scoreRange = [0]
    label = []
    min_score = float('inf')
    max_score = 0
    mean_score = 0
    total_score = 0
    total_student = 0
    i = 0
    index = 0
    while i <= int(assignment.getMaxScore()):
        range = str(i) + " - " + str(i + 5)
        label.append(range)
        for s in course.getStudents():
            studentAssignment = s.getCoursefromid(int(course_id), int(course_sec)).getAssignment(code)
            if isinstance(studentAssignment, StudentAssignment):
                if i <= studentAssignment.getScore() < (i + 5):
                    if len(scoreRange) == index:
                        scoreRange.append(1)
                    else:
                        scoreRange[index] += 1
                else:
                    if len(scoreRange) == index:
                        scoreRange.append(0)
        i += 5
        index += 1
            
    for s in course.getStudents():
        student = {}
        student["name"] = s.getFirstName() + " " + s.getLastName()
        assignments = s.getCoursefromid(int(course_id), int(course_sec)).getAssignments()
        for a in assignments:
            if a.getCode() == code:
                if isinstance(a, StudentAssignment):
                    if a.getStatus() == "Graded":
                        student["score"] = a.getScore()
                        total_score += a.getScore()
                        total_student += 1
                        if a.getScore() < min_score:
                            min_score = a.getScore()
                        if a.getScore() > max_score:
                            max_score = a.getScore()
                    else:
                        student["score"] = "Not graded"
                else:
                    student["score"] = 0
        students[s.getId()] = student
    if total_student != 0:
        mean_score = total_score / total_student
            
    return templates.TemplateResponse("grade_assignment_teacher.html", {"request": request, "email": user.getEmail(), "course_id": course_id, "course_sec": course_sec, "course_name": course.getName(), "studentDict": students, "code": code, "topic": course.getAssignment(code).getName(), "total_score": course.getAssignment(code).getMaxScore(), "percentage": course.getAssignment(code).getWeight(), "min_score": min_score, "max_score": max_score, "mean_score": mean_score, "score_range": scoreRange, "score_label": label})

# teacher's grade over
@app.get("/Teacher/grade-overview/", response_class=HTMLResponse)
async def teacher_grade_overview(request: Request, user=Depends(manager)):
    courses = {}
    userCourses = user.getTeaches()
    
    for c in userCourses:
        course = {}
        course["name"] = c.getName()
        course["sec"] = c.getSection()
        course["credit"] = c.getCredit()
        course["min_score"] = float(c.getMin())
        course["max_score"] = float(c.getMax())
        course["mean_score"] = c.getMean()
        courses[c.getId()] = course
    
    return templates.TemplateResponse("grade_overview_teacher.html", {"request": request, "email": user.getEmail(), "courseDict": courses})

# profile page for user
@app.get("/profile")
async def profile(request: Request, user=Depends(manager)):
    if isinstance(user, Student):
        return templates.TemplateResponse("profile_student.html", {"request": request, "email": user.getEmail(), "first_name": user.getFirstName(), "last_name": user.getLastName(), "id": user.getId()})
    return templates.TemplateResponse("profile_teacher.html", {"request": request, "email": user.getEmail(), "first_name": user.getFirstName(), "last_name": user.getLastName()})

# redirect to login page and delete user's cookie
@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("session")
    return response
