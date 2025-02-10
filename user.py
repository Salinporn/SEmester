import persistent

class Announcement(persistent.Persistent):
    def __init__(self, topic, content, date, file):
        self.topic = topic
        self.content = content
        self.date = date
        self.file = file
    
    def getTopic(self):
        return self.topic
    
    def getContent(self):
        return self.content
    
    def getDate(self):
        return self.date
    
    def getFilename(self):
        return self.file

class Attendance(persistent.Persistent):
    def __init__(self, date):
        self.date = date
        self.totalPresent = 0
        self.totalLate = 0
        self.totalAbsent = 0
    
    def getDate(self):
        return self.date

    def getTotalPresent(self):
        return self.totalPresent

    def getTotalLate(self):
        return self.totalLate
    
    def getTotalAbsent(self):
        return self.totalAbsent
    
    def setTotalPresent(self, total):
        self.totalPresent = total
        self._p_changed = True

    def setTotalLate(self, total):
        self.totalLate = total
        self._p_changed = True

    def setTotalAbsent(self, total):
        self.totalAbsent = total
        self._p_changed = True
    
class StudentAttendance(Attendance, persistent.Persistent):
    def __init__(self, date):
        super().__init__(date)
        self.status = "absent"
        self.remark = ""
    
    def setStatus(self, status):
        self.status = status
    
    def setRemark(self, remark):
        self.remark = remark
    
    def getStatus(self):
        return self.status
    
    def getRemark(self):
        return self.remark
    
class Assignment(persistent.Persistent):
    def __init__(self, name, maxScore, weight, dueDate, dueTime, file, description, code):
        self.name = name
        self.maxScore = maxScore
        self.weight = weight
        self.dueDate = dueDate
        self.dueTime = dueTime
        self.file = file
        self.description = description
        self.code = code
    
    def getName(self):
        return self.name
    
    def getMaxScore(self):
        return self.maxScore
    
    def getWeight(self):
        return self.weight
    
    def getDueDate(self):
        return self.dueDate
    
    def getDueTime(self):
        return self.dueTime
    
    def getFilename(self):
        return self.file
    
    def getDescription(self):
        return self.description
    
    def getCode(self):
        return self.code
    
class StudentAssignment(Assignment):
    def __init__(self, name, maxScore, weight, dueDate, dueTime, file, description, code, submitDate, submitTime):
        super().__init__(name, maxScore, weight, dueDate, dueTime, file, description, code)
        self.submitDate = submitDate
        self.submitTime = submitTime
        self.score = 0
        self.comment = ""
        self.status = "Submitted"
        
    def getScore(self):
        return self.score
    
    def getComment(self):
        return self.comment

    def getScorebyWeight(self):
        return self.score * float(self.weight) / float(self.maxScore)

    def getSubmitDate(self):
        return self.submitDate
    
    def getSubmitTime(self):
        return self.submitTime
        
    def setScore(self, score):
        self.score = score
    
    def setComment(self, comment):
        self.comment = comment
        
    def setStatus(self, status):
        self.status = status
    
    def getStatus(self):
        return self.status
    
class Course(persistent.Persistent):
    def __init__(self, name, id, sec, code, credit, teacher):
        self.name = name
        self.id = id
        self.credit = credit
        self.teacher = teacher
        self.code = code
        self.announcements = []
        self.assignments = []
        self.gradeScheme = {}
        self.sec = sec
        self.attendances = []
    
    def getName(self):
        return self.name
    
    def getId(self):
        return self.id
    
    def getSection(self):
        return self.sec
    
    def getCode(self):
        return self.code
    
    def getCredit(self):
        return self.credit
    
    def getTeacher(self):
        return self.teacher
    
    def getAssignments(self):
        return self.assignments
    
    def getAssignment(self, code):
        for a in self.assignments:
            if a.getCode() == code:
                return a
    
    def getGradeScheme(self):
        return self.gradeScheme

    def getAnnouncements(self):
        return self.announcements
    
    def setGradeScheme(self, gradeScheme):
        self.gradeScheme = gradeScheme
        self._p_changed = True
    
    def addAssignment(self, assignment):
        self.assignments.append(assignment)
        self._p_changed = True
    
    def removeAssignment(self, assignment):
        self.assignments.remove(assignment)
        self._p_changed = True
    
    def addAnnouncement(self, announcement):
        self.announcements.append(announcement)
        self._p_changed = True
    
    def removeAnnouncement(self, announcement):
        self.announcements.remove(announcement)
        self._p_changed = True

    def getAttendances(self):
        return self.attendances
    
    def addAttendance(self, attendance):
        self.attendances.append(attendance)
        self._p_changed = True

    def removeAttendance(self, attendance):
        self.attendances.remove(attendance)
        self._p_changed = True

    def getAttendance(self, date):
        for a in self.attendances:
            if a.getDate() == date:
                return a

    
class StudentCourse(Course,persistent.Persistent):
    def __init__(self, name, id, sec, code, credit, teacher):
        super().__init__(name, id, sec, code, credit, teacher)
        self.score = 0
        self.grade = ""
        
    def getScore(self):
        return self.score
    
    def getGrade(self):
        for g in self.gradeScheme:
            if g["min"] <= self.score <= g["max"]:
                return g["Grade"]
        return "F"
    
    def replaceAssignment(self, assignment):
        for a in self.assignments:
            if a.getCode() == assignment.getCode():
                self.assignments.remove(a)
                self.assignments.append(assignment)
                self._p_changed = True
                break
    
    def getGrade(self):
        return self.grade
    
    def setGrade(self, grade):
        self.grade = grade
        
    def getTotalScore(self):
        totalScore = 0
        for a in self.assignments:
            if isinstance(a, StudentAssignment):
                if a.getStatus() == "Graded":
                    totalScore += a.getScorebyWeight()
        return totalScore
    
class TeacherCourse(Course, persistent.Persistent):
    def __init__(self, name, id, sec, code, credit, teacher):
        super().__init__(name, id, sec, code, credit, teacher)
        self.students = []
        self.dates = []
        
    def addStudent(self, student):
        self.students.append(student)
        self._p_changed = True
        for an in self.announcements:
            student.getCourse(self.code).addAnnouncement(an)
        for asg in self.assignments:
            student.getCourse(self.code).addAssignment(asg)
        for a in self.attendances:
            attendance = StudentAttendance(a.getDate())
            student.getCourse(self.code).addAttendance(attendance)
        student.getCourse(self.code).setGradeScheme(self.gradeScheme)
    
    def removeStudent(self, student):
        self.students.remove(student)
        self._p_changed = True
    
    def getStudents(self):
        return self.students
    
    def getStudent(self, id):
        for s in self.students:
            if s.getId() == id:
                return s
            
    def getMin(self):
        min = ""
        for s in self.students:
            studentCourse = s.getCourse(self.code)
            if min == "":
                min = studentCourse.getTotalScore()
            elif studentCourse.getTotalScore() < min:
                min = studentCourse.getTotalScore()
        return min
    
    def getMax(self):
        max = ""
        for s in self.students:
            studentCourse = s.getCourse(self.code)
            if max == "":
                max = studentCourse.getTotalScore()
            elif studentCourse.getTotalScore() > max:
                max = studentCourse.getTotalScore()
        return max

    def getMean(self):
        totalScore = 0
        totalStudent = 0
        for s in self.students:
            totalScore += s.getCourse(self.code).getTotalScore()
            totalStudent += 1
        return totalScore / totalStudent
    
    def getSD(self):
        mean = self.getMean()
        totalScore = 0
        totalStudent = 0
        for s in self.students:
            totalScore += (s.getCourse(self.code).getTotalScore() - mean) ** 2
            totalStudent += 1
        return (totalScore / totalStudent) ** 0.5
    
class User(persistent.Persistent):
    def __init__(self, first_name, last_name, email, password):
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.password = password
        
    def getFirstName(self):
        return self.first_name
    
    def getLastName(self):
        return self.last_name

    def getEmail(self):
        return self.email
    
    def getPassword(self):
        return self.password
    
    
class Student(User, persistent.Persistent):
    def __init__(self, first_name, last_name, id, email, password):
        super().__init__(first_name, last_name, email, password)
        self.id = id
        self.enrolls = []
    
    def getId(self):
        return self.id
    
    def getEnrolls(self):
        return self.enrolls
    
    def addEnrolls(self, course):
        self.enrolls.append(course)
        self._p_changed = True
        
    def removeEnrolls(self, course):
        self.enrolls.remove(course)
        self._p_changed = True
    
    def getCoursefromid(self, id, sec):
        for c in self.enrolls:
            if c.getId() == id and c.getSection() == sec:
                return c
            
    def getCourse(self, code):
        for c in self.enrolls:
            if c.getCode() == code:
                return c
    
class Teacher(User, persistent.Persistent):
    def __init__(self, first_name, last_name, email, password):
        super().__init__(first_name, last_name, email, password)
        self.teaches = []
        
    def getTeaches(self):
        return self.teaches
    
    def getCourse(self, id, sec):
        for c in self.teaches:
            if c.getId() == id and c.getSection() == sec:
                return c

    def addTeaches(self, course):
        self.teaches.append(course)
        self._p_changed = True