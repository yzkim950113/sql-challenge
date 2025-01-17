from flask import Flask, render_template, request, redirect, url_for, flash, session
from datetime import datetime, timedelta
from db_utils import execute_with_retry, executemany_with_retry, get_db_connection
import sqlite3
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# 관리자 권한 설정
ADMIN_ID = "admin"
ADMIN_PASSWORD = "admin123"

# 관리자 권한 데코레이터
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash('관리자 권한이 필요합니다.', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def create_problems(c):
    """각 회차별 문제를 생성하고 데이터베이스에 추가하는 함수"""
    # 1회차: SELECT, FROM만 사용
    problems_round1 = [
        (1, "employees 테이블에서 모든 직원의 이름을 조회하시오.", 
            "SELECT name FROM employees",
            "최하",
            """[테이블 데이터]
employees 테이블:
name    department  salary
Alice   IT         60000
Bob     HR         55000
Carol   IT         65000

[실행 결과]
name
-----
Alice
Bob
Carol"""),
            
        (1, "employees 테이블에서 직원의 이름과 부서를 조회하시오.",
            "SELECT name, department FROM employees",
            "하",
            """[테이블 데이터]
employees 테이블:
name    department  salary
Alice   IT         60000
Bob     HR         55000
Carol   IT         65000

[실행 결과]
name    department
-----   ----------
Alice   IT
Bob     HR
Carol   IT"""),
            
        (1, "employees 테이블의 모든 컬럼을 조회하시오.",
            "SELECT * FROM employees",
            "중",
            """[테이블 데이터]
employees 테이블:
name    department  salary
Alice   IT         60000
Bob     HR         55000
Carol   IT         65000

[실행 결과]
name    department  salary
-----   ----------  ------
Alice   IT         60000
Bob     HR         55000
Carol   IT         65000""")
    ]

    # 2회차: WHERE 추가 (SELECT, FROM, WHERE 사용 가능)
    problems_round2 = [
        (2, "직원(employees) 테이블에서 IT 부서에 근무하는 직원들의 이름을 조회하시오.",
            "SELECT name FROM employees WHERE department = 'IT'",
            "최하",
            """[테이블 데이터]
employees 테이블:
name    department  salary
Alice   IT         60000
Bob     HR         55000
Carol   IT         65000
David   Marketing  58000

[실행 결과]
name
-----
Alice
Carol"""),
            
        (2, "직원(employees) 테이블에서 급여(salary)가 60000 이상인 직원의 이름과 급여를 조회하시오.",
            "SELECT name, salary FROM employees WHERE salary >= 60000",
            "하",
            """[테이블 데이터]
employees 테이블:
name    department  salary
Alice   IT         60000
Bob     HR         55000
Carol   IT         65000
David   Marketing  58000

[실행 결과]
name    salary
-----   ------
Alice   60000
Carol   65000"""),
            
        (2, "직원(employees) 테이블에서 IT 부서이면서 급여가 63000 이상인 직원의 이름과 급여를 조회하시오.",
            "SELECT name, salary FROM employees WHERE department = 'IT' AND salary >= 63000",
            "중",
            """[테이블 데이터]
employees 테이블:
name    department  salary
Alice   IT         60000
Bob     HR         55000
Carol   IT         65000
David   Marketing  58000

[실행 결과]
name    salary
-----   ------
Carol   65000""")
    ]

    # 3회차: GROUP BY, HAVING, ORDER BY 추가
    problems_round3 = [
        (3, "각 부서별 직원 수를 구하고, 부서 이름으로 정렬하시오.",
            "SELECT department, COUNT(*) as emp_count FROM employees GROUP BY department ORDER BY department",
            "최하",
            """[테이블 데이터]
employees 테이블:
name    department  salary
Alice   IT         60000
Bob     HR         55000
Carol   IT         65000
David   Marketing  58000
Eve     IT         62000

[실행 결과]
department  emp_count
----------  ---------
HR          1
IT          3
Marketing   1"""),
            
        (3, "부서별 평균 급여가 60000 이상인 부서들을 조회하시오.",
            "SELECT department, AVG(salary) as avg_salary FROM employees GROUP BY department HAVING AVG(salary) >= 60000",
            "하",
            """[테이블 데이터]
employees 테이블:
name    department  salary
Alice   IT         60000
Bob     HR         55000
Carol   IT         65000
David   Marketing  58000
Eve     IT         62000

[실행 결과]
department  avg_salary
----------  ----------
IT          62333.33"""),
            
        (3, "부서별 최고 급여를 구하고, 최고 급여가 높은 순서대로 정렬하시오.",
            "SELECT department, MAX(salary) as max_salary FROM employees GROUP BY department ORDER BY max_salary DESC",
            "중",
            """[테이블 데이터]
employees 테이블:
name    department  salary
Alice   IT         60000
Bob     HR         55000
Carol   IT         65000
David   Marketing  58000
Eve     IT         62000

[실행 결과]
department  max_salary
----------  ----------
IT          65000
Marketing   58000
HR          55000""")
    ]

    # 4회차: 조건분기, 형태변환, 날짜, 문자 추가
    problems_round4 = [
        (4, "직원들의 급여를 'High'(60000 이상), 'Low'(60000 미만)로 분류하여 이름, 급여, 급여수준을 조회하고 이름순으로 정렬하시오.",
            "SELECT name, salary, CASE WHEN salary >= 60000 THEN 'High' ELSE 'Low' END as salary_level FROM employees ORDER BY name",
            "최하",
            """[테이블 데이터]
employees 테이블:
name    salary    hire_date
Alice   60000    2023-01-15
Bob     55000    2023-02-20
Carol   65000    2023-03-10
David   58000    2023-04-05

[실행 결과]
name    salary    salary_level
-----   ------    ------------
Alice   60000     High
Bob     55000     Low
Carol   65000     High
David   58000     Low"""),
            
        (4, "직원들의 입사 연도와 월을 조회하고, 입사일 순서로 정렬하시오.",
            "SELECT name, strftime('%Y', hire_date) as year, strftime('%m', hire_date) as month FROM employees ORDER BY hire_date",
            "하",
            """[테이블 데이터]
employees 테이블:
name    salary    hire_date
Alice   60000    2023-01-15
Bob     55000    2023-02-20
Carol   65000    2023-03-10
David   58000    2023-04-05

[실행 결과]
name    year    month
-----   ----    -----
Alice   2023    01
Bob     2023    02
Carol   2023    03
David   2023    04"""),
            
        (4, "직원의 이름을 대문자로 변환하고, 근무 개월 수를 계산하여 조회하시오. 근무 개월 수가 많은 순서대로 정렬하시오.",
            "SELECT UPPER(name) as name, ROUND((JULIANDAY('now') - JULIANDAY(hire_date))/30) as months_worked FROM employees ORDER BY months_worked DESC",
            "중",
            """[테이블 데이터]
employees 테이블:
name    salary    hire_date
Alice   60000    2023-01-15
Bob     55000    2023-02-20
Carol   65000    2023-03-10
David   58000    2023-04-05

[실행 결과]
name    months_worked
-----   -------------
ALICE   24
BOB     23
CAROL   22
DAVID   21""")
    ]

    # 5회차: JOIN 기본
    problems_round5 = [
        (5, "직원들의 이름과 소속 부서명을 조회하시오. 부서명순으로 정렬하시오.",
            "SELECT e.name, d.dept_name FROM employees e JOIN departments d ON e.dept_id = d.id ORDER BY d.dept_name",
            "최하",
            """[테이블 데이터]
employees 테이블:        departments 테이블:
id  name    dept_id    id  dept_name
1   Alice   1          1   IT
2   Bob     2          2   HR
3   Carol   1          3   Marketing
4   David   3

[실행 결과]
name    dept_name
-----   ---------
Bob     HR
Alice   IT
Carol   IT
David   Marketing"""),
            
        (5, "모든 부서의 부서명과 소속 직원 수를 조회하시오. 직원이 없는 부서도 포함하시오.",
            "SELECT d.dept_name, COUNT(e.id) as emp_count FROM departments d LEFT JOIN employees e ON d.id = e.dept_id GROUP BY d.id ORDER BY d.dept_name",
            "하",
            """[테이블 데이터]
employees 테이블:        departments 테이블:
id  name    dept_id    id  dept_name
1   Alice   1          1   IT
2   Bob     2          2   HR
3   Carol   1          3   Marketing
4   David   3          4   Finance

[실행 결과]
dept_name    emp_count
---------    ---------
Finance      0
HR           1
IT           2
Marketing    1"""),
            
        (5, "부서별로 소속 직원의 평균 급여를 구하고, 평균 급여가 높은 순서대로 정렬하시오.",
            "SELECT d.dept_name, AVG(e.salary) as avg_salary FROM departments d JOIN employees e ON d.id = e.dept_id GROUP BY d.id ORDER BY avg_salary DESC",
            "중",
            """[테이블 데이터]
employees 테이블:        departments 테이블:
id  name    dept_id  salary    id  dept_name
1   Alice   1        60000     1   IT
2   Bob     2        55000     2   HR
3   Carol   1        65000     3   Marketing
4   David   3        58000     4   Finance

[실행 결과]
dept_name    avg_salary
---------    ----------
IT           62500
Marketing    58000
HR           55000""")
    ]

    # 6회차: JOIN 심화
    problems_round6 = [
        (6, "직원의 이름, 부서명, 프로젝트명을 조회하시오. 프로젝트에 참여하지 않은 직원도 출력하시오.",
            "SELECT e.name, d.dept_name, p.proj_name FROM employees e JOIN departments d ON e.dept_id = d.id LEFT JOIN projects p ON e.proj_id = p.id ORDER BY e.name",
            "최하",
            """[테이블 데이터]
employees 테이블:    departments 테이블:    projects 테이블:
name  dept_id proj_id  id  dept_name         id  proj_name
Alice 1       1        1   IT                1   Alpha
Bob   2       null     2   HR                2   Beta
Carol 1       2        3   Marketing         3   Gamma
David 3       1

[실행 결과]
name    dept_name    proj_name
-----   ---------    ---------
Alice   IT           Alpha
Bob     HR           null
Carol   IT           Beta
David   Marketing    Alpha"""),
            
        (6, "프로젝트별로 참여하는 부서의 수를 조회하시오. 참여 부서가 없는 프로젝트도 포함하시오.",
            "SELECT p.proj_name, COUNT(DISTINCT e.dept_id) as dept_count FROM projects p LEFT JOIN employees e ON p.id = e.proj_id GROUP BY p.id ORDER BY p.proj_name",
            "하",
            """[테이블 데이터]
employees 테이블:    departments 테이블:    projects 테이블:
name  dept_id proj_id  id  dept_name         id  proj_name
Alice 1       1        1   IT                1   Alpha
Bob   2       1        2   HR                2   Beta
Carol 1       2        3   Marketing         3   Gamma
David 3       1

[실행 결과]
proj_name    dept_count
---------    ----------
Alpha        3
Beta         1
Gamma        0"""),
            
        (6, "각 부서별로 다른 부서와 함께 진행하는 프로젝트 수를 조회하시오.",
            """WITH dept_projects AS (
    SELECT DISTINCT d1.id as dept_id, d1.dept_name, p.id as proj_id
    FROM departments d1 
    JOIN employees e1 ON d1.id = e1.dept_id 
    JOIN projects p ON e1.proj_id = p.id
)
SELECT 
    d.dept_name,
    COUNT(DISTINCT CASE 
        WHEN EXISTS (
            SELECT 1 FROM dept_projects dp2 
            WHERE dp2.proj_id = dp1.proj_id 
            AND dp2.dept_id != d.id
        ) THEN dp1.proj_id 
    END) as collab_projects
FROM departments d
LEFT JOIN dept_projects dp1 ON d.id = dp1.dept_id
GROUP BY d.id
ORDER BY collab_projects DESC""",
            "중",
            """[테이블 데이터]
employees 테이블:    departments 테이블:    projects 테이블:
name  dept_id proj_id  id  dept_name         id  proj_name
Alice 1       1        1   IT                1   Alpha
Bob   2       1        2   HR                2   Beta
Carol 1       2        3   Marketing         3   Gamma
David 3       1

[실행 결과]
dept_name    collab_projects
---------    ---------------
IT           2
HR           1
Marketing    1""")
    ]

    # 7회차: WITH
    problems_round7 = [
        (7, "WITH 구문을 사용하여 부서별 평균 급여를 구하고, 그 중에서 평균 급여가 60000 이상인 부서에 속한 직원들의 정보를 조회하시오.",
            """WITH dept_avg AS (
    SELECT dept_id, AVG(salary) as avg_salary
    FROM employees 
    GROUP BY dept_id
    HAVING AVG(salary) >= 60000
)
SELECT e.name, d.dept_name, e.salary
FROM employees e
JOIN departments d ON e.dept_id = d.id
JOIN dept_avg da ON e.dept_id = da.dept_id
ORDER BY e.salary DESC""",
            "최하",
            """[테이블 데이터]
employees 테이블:
id  name    dept_id  salary    departments 테이블:
1   Alice   1        62000     id  dept_name
2   Bob     2        55000     1   IT
3   Carol   1        65000     2   HR
4   David   2        57000     3   Marketing
5   Eve     1        63000

[실행 결과]
name    dept_name    salary
-----   ---------    -------
Carol   IT           65000
Eve     IT           63000
Alice   IT           62000"""),

        (7, "WITH 구문을 사용하여 직전 월의 급여 대비 인상된 직원들의 명단과 인상률을 조회하시오.",
            """WITH monthly_salary AS (
    SELECT 
        employee_id,
        payment_date,
        salary,
        LAG(salary) OVER (PARTITION BY employee_id ORDER BY payment_date) as prev_salary
    FROM salary_history
)
SELECT 
    e.name,
    ms.payment_date,
    ms.prev_salary as previous_salary,
    ms.salary as current_salary,
    ROUND((ms.salary - ms.prev_salary) * 100.0 / ms.prev_salary, 1) as increase_percent
FROM monthly_salary ms
JOIN employees e ON ms.employee_id = e.id
WHERE ms.salary > ms.prev_salary
ORDER BY increase_percent DESC""",
            "하",
            """[테이블 데이터]
salary_history 테이블:        employees 테이블:
employee_id  payment_date  salary     id  name
1           2024-01-15    62000      1   Alice
1           2024-02-15    65000      2   Bob
2           2024-01-15    55000      3   Carol
2           2024-02-15    55000
3           2024-01-15    58000
3           2024-02-15    61000

[실행 결과]
name    payment_date    previous_salary    current_salary    increase_percent
-----   ------------    ---------------    --------------    ----------------
Alice   2024-02-15     62000             65000             4.8
Carol   2024-02-15     58000             61000             5.2"""),

        (7, "WITH 구문을 사용하여 각 부서별로 급여 순위를 매기고, 부서별 상위 2명의 직원 정보와 전체 직원 중 급여 순위를 함께 조회하시오.",
            """WITH ranked_by_dept AS (
    SELECT 
        e.name,
        d.dept_name,
        e.salary,
        RANK() OVER (PARTITION BY e.dept_id ORDER BY salary DESC) as dept_rank,
        RANK() OVER (ORDER BY salary DESC) as overall_rank
    FROM employees e
    JOIN departments d ON e.dept_id = d.id
)
SELECT *
FROM ranked_by_dept
WHERE dept_rank <= 2
ORDER BY dept_name, dept_rank""",
            "중",
            """[테이블 데이터]
employees 테이블:        departments 테이블:
id  name    dept_id  salary    id  dept_name
1   Alice   1        62000     1   IT
2   Bob     2        55000     2   HR
3   Carol   1        65000     3   Marketing
4   David   2        57000
5   Eve     1        63000
6   Frank   3        59000
7   Grace   3        61000

[실행 결과]
name    dept_name    salary    dept_rank    overall_rank
-----   ---------    ------    ---------    ------------
David   HR           57000     1            6
Bob     HR           55000     2            7
Carol   IT           65000     1            1
Eve     IT           63000     2            3
Grace   Marketing    61000     1            4
Frank   Marketing    59000     2            5""")
    ]

    # 모든 문제를 데이터베이스에 삽입
    all_problems = (problems_round1 + problems_round2 + problems_round3 + 
                   problems_round4 + problems_round5 + problems_round6 + problems_round7)
    
    for round_id, question, correct_query, difficulty, sample_data in all_problems:
        c.execute('''
            INSERT INTO problems (round_id, question, correct_query, difficulty, sample_data)
            VALUES (?, ?, ?, ?, ?)
        ''', (round_id, question, correct_query, difficulty, sample_data))


# 데이터베이스 초기화 및 기본 데이터 생성
def init_db():
    conn = sqlite3.connect('sql_challenge.db')
    c = conn.cursor()
    
    # 모든 테이블 삭제 (초기화)
    c.execute("DROP TABLE IF EXISTS user_progress")
    c.execute("DROP TABLE IF EXISTS problems")
    c.execute("DROP TABLE IF EXISTS rounds")
    
    # 회차 테이블
    c.execute('''
        CREATE TABLE rounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            round_number INTEGER UNIQUE NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL
        )
    ''')
    
    # 문제 테이블
    c.execute('''
        CREATE TABLE problems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            round_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            correct_query TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            sample_data TEXT,
            FOREIGN KEY (round_id) REFERENCES rounds(id)
        )
    ''')
    
    # 사용자 진행상황 테이블
    c.execute('''
        CREATE TABLE user_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            problem_id INTEGER NOT NULL,
            is_correct BOOLEAN NOT NULL DEFAULT 0,
            last_attempt TEXT,
            completed_at TEXT,
            attempts INTEGER DEFAULT 0,
            last_wrong_query TEXT,
            last_wrong_result TEXT,
            FOREIGN KEY (problem_id) REFERENCES problems(id)
        )
    ''')
    
    # 초기 데이터 생성 - 2025년 1월 20일부터 시작
    start_date = datetime(2025, 1, 10, 0, 0, 0)  # 1월 20일 00:00:00
    
    # 7회차 생성
    for i in range(7):
        round_start = start_date + timedelta(days=i*3)
        round_end = round_start + timedelta(days=3) - timedelta(seconds=1)  # 23:59:59로 설정
        
        # ISO 형식으로 저장
        c.execute('''
            INSERT INTO rounds (round_number, start_date, end_date)
            VALUES (?, ?, ?)
        ''', (
            i+1, 
            round_start.strftime('%Y-%m-%dT%H:%M:%S'),
            round_end.strftime('%Y-%m-%dT%H:%M:%S')
        ))
    
    # 문제 생성 함수 호출
    create_problems(c)
    
    conn.commit()
    conn.close()

# 유틸리티 함수들
def get_round_status():
    conn = sqlite3.connect('sql_challenge.db')
    c = conn.cursor()
    today = datetime.now()
    
    c.execute('''
        SELECT 
            r.id,
            r.round_number,
            r.start_date,
            r.end_date,
            COUNT(DISTINCT p.id) as total_problems,
            COUNT(DISTINCT CASE WHEN up.is_correct = 1 THEN p.id END) as solved_problems
        FROM rounds r
        LEFT JOIN problems p ON r.id = p.round_id
        LEFT JOIN user_progress up ON p.id = up.problem_id AND up.user_id = ?
        GROUP BY r.id
        ORDER BY r.round_number
    ''', (session['user_id'],))
    
    rows = c.fetchall()
    rounds = []
    
    for row in rows:
        round_id, round_number, start_date, end_date, total_problems, solved_problems = row
        start_date = datetime.strptime(start_date.replace('T', ' '), '%Y-%m-%d %H:%M:%S')
        end_date = datetime.strptime(end_date.replace('T', ' '), '%Y-%m-%d %H:%M:%S')
        
        status = 'locked'
        if today >= start_date and today <= end_date:
            status = 'active'
        elif today > end_date:
            status = 'closed'
            
        rounds.append({
            'id': round_id,
            'number': round_number,
            'start_date': start_date,
            'end_date': end_date,
            'status': status,
            'problems': total_problems,
            'solved': solved_problems or 0
        })
    
    conn.close()
    return rounds

def parse_sample_data(sample_data):
    """샘플 데이터 문자열에서 테이블 정보를 추출"""
    tables_data = []
    current_table = None
    columns = []
    rows = []
    
    lines = sample_data.split('\n')
    for line in lines:
        line = line.strip()
        if '테이블:' in line:
            if current_table:
                tables_data.append((current_table, columns, rows))
            current_table = line.split('테이블:')[0].strip()
            columns = []
            rows = []
        elif line and current_table and not columns:
            columns = [col.strip() for col in line.split()]
        elif line and columns and set(line) != {'-'}:
            row_data = line.split()
            if len(row_data) == len(columns):
                rows.append(row_data)
    
    if current_table:
        tables_data.append((current_table, columns, rows))
    
    return tables_data

def format_query_result(rows, col_names=None):
    """쿼리 결과를 보기 좋게 포맷팅"""
    if not rows:
        return "결과가 없습니다."
    
    if col_names is None:
        return "\n".join(" | ".join(str(cell) for cell in row) for row in rows)
    
    result = [" | ".join(col_names)]
    result.append("-" * (sum(len(col) for col in col_names) + 3 * (len(col_names) - 1)))
    
    for row in rows:
        result.append(" | ".join(str(cell) for cell in row))
    
    return "\n".join(result)

def normalize_result(result):
    """쿼리 결과를 정규화하여 비교"""
    return [tuple(str(cell).lower().strip() if cell is not None else '' for cell in row) for row in result]

# 라우트 함수들
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    rounds = get_round_status()
    return render_template('index.html', rounds=rounds)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_id = request.form['user_id']
        session['user_id'] = user_id
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/round/<int:round_id>')
def view_round(round_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # 라운드 정보 조회
            execute_with_retry(c, '''
                SELECT id, round_number, start_date, end_date
                FROM rounds 
                WHERE id = ?
            ''', (round_id,))
            round_data = c.fetchone()
            
            if not round_data:
                flash('존재하지 않는 라운드입니다.', 'error')
                return redirect(url_for('index'))
            
            # 문제 목록 조회
            execute_with_retry(c, '''
                WITH latest_progress AS (
                    SELECT 
                        problem_id,
                        is_correct,
                        completed_at,
                        attempts,
                        last_wrong_query,
                        last_wrong_result,
                        ROW_NUMBER() OVER (PARTITION BY problem_id ORDER BY last_attempt DESC) as rn
                    FROM user_progress
                    WHERE user_id = ?
                )
                SELECT 
                    p.id,
                    p.question,
                    p.difficulty,
                    p.sample_data,
                    COALESCE(lp.is_correct, 0) as solved,
                    lp.completed_at,
                    COALESCE(lp.attempts, 0) as attempts,
                    lp.last_wrong_query,
                    lp.last_wrong_result
                FROM problems p
                LEFT JOIN latest_progress lp ON p.id = lp.problem_id AND lp.rn = 1
                WHERE p.round_id = ?
                ORDER BY p.id
            ''', (session['user_id'], round_id))
            
            problems = []
            for row in c.fetchall():
                problems.append({
                    'id': row[0],
                    'question': row[1],
                    'difficulty': row[2],
                    'sample_data': row[3],
                    'solved': bool(row[4]),
                    'completed_at': row[5],
                    'attempts': row[6],
                    'last_wrong_query': row[7],
                    'last_wrong_result': row[8]
                })
            
            # 날짜 파싱
            start_date = datetime.strptime(round_data[2].replace('T', ' '), '%Y-%m-%d %H:%M:%S')
            end_date = datetime.strptime(round_data[3].replace('T', ' '), '%Y-%m-%d %H:%M:%S')
            
            round_info = {
                'id': round_data[0],
                'number': round_data[1],
                'start_date': start_date,
                'end_date': end_date,
                'status': 'active' if datetime.now() <= end_date else 'closed'
            }
            
            return render_template('round.html', round=round_info, problems=problems)
            
    except sqlite3.Error as e:
        flash('데이터베이스 오류가 발생했습니다.', 'error')
        return redirect(url_for('index'))

@app.route('/submit', methods=['POST'])
def submit():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    problem_id = request.form.get('problem_id')
    user_query = request.form.get('user_query')
    round_id = request.form.get('round_id')
    
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # 라운드 활성화 상태 확인
            execute_with_retry(c, '''
                SELECT r.end_date, p.sample_data, p.correct_query
                FROM rounds r
                JOIN problems p ON r.id = p.round_id
                WHERE p.id = ?
            ''', (problem_id,))
            
            row = c.fetchone()
            if not row:
                flash('문제를 찾을 수 없습니다.', 'error')
                return redirect(url_for('view_round', round_id=round_id))
                
            end_date, sample_data, correct_query = row
            end_date = datetime.strptime(end_date.replace('T', ' '), '%Y-%m-%d %H:%M:%S')
            
            if datetime.now() > end_date:
                flash('이 라운드는 이미 종료되었습니다.', 'error')
                return redirect(url_for('view_round', round_id=round_id))
            
            # 쿼리 실행 및 검증
            test_conn = sqlite3.connect(':memory:')
            test_c = test_conn.cursor()
            
            try:
                # 테스트 데이터베이스 설정
                tables_data = parse_sample_data(sample_data)
                for table_name, columns, rows in tables_data:
                    create_table_query = f"CREATE TABLE {table_name} ({', '.join(columns)})"
                    test_c.execute(create_table_query)
                    
                    if rows:
                        placeholders = ', '.join(['?' for _ in columns])
                        insert_query = f"INSERT INTO {table_name} VALUES ({placeholders})"
                        test_c.executemany(insert_query, rows)
                
                # 쿼리 실행
                test_c.execute(user_query)
                user_result = test_c.fetchall()
                col_names = [description[0] for description in test_c.description] if test_c.description else None
                
                test_c.execute(correct_query)
                correct_result = test_c.fetchall()
                
                is_correct = (normalize_result(user_result) == normalize_result(correct_result))
                user_result_str = format_query_result(user_result, col_names)
                
            except sqlite3.Error as e:
                is_correct = False
                user_result_str = f"SQL 오류: {str(e)}"
            finally:
                test_conn.close()
            
            # 이전 정답 확인
            execute_with_retry(c, '''
                INSERT OR REPLACE INTO user_progress 
                (user_id, problem_id, is_correct, last_attempt, completed_at, attempts, last_wrong_query, last_wrong_result)
                VALUES (?, ?, ?, ?, ?, 
                    COALESCE((SELECT attempts + 1 FROM user_progress 
                              WHERE user_id = ? AND problem_id = ?), 1),
                    ?, ?)
            ''', (
                session['user_id'], 
                problem_id,
                is_correct,
                datetime.now().isoformat(),
                datetime.now().isoformat() if is_correct else None,
                session['user_id'],
                problem_id,
                None if is_correct else user_query,
                None if is_correct else user_result_str
            ))
            
            if is_correct:
                flash('정답입니다!', 'success')
            else:
                flash('틀렸습니다.', 'error')
            
            return redirect(url_for('view_round', round_id=round_id))
            
    except sqlite3.Error as e:
        flash('데이터베이스 오류가 발생했습니다.', 'error')
        return redirect(url_for('view_round', round_id=round_id))

# 관리자 라우트
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        password = request.form.get('password')
        
        if user_id == ADMIN_ID and password == ADMIN_PASSWORD:
            session['is_admin'] = True
            return redirect(url_for('admin_check'))
        else:
            flash('잘못된 관리자 정보입니다.', 'error')
    
    return render_template('admin_login.html')

@app.route('/admin/check')
@admin_required
def admin_check():
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # 모든 사용자 목록 가져오기
            execute_with_retry(c, '''
                SELECT DISTINCT user_id 
                FROM user_progress 
                ORDER BY user_id
            ''')
            users = c.fetchall()
            
            user_progress = []
            for (user_id,) in users:
                # 각 회차별 해결한 문제 수 계산
                execute_with_retry(c, '''
                    SELECT r.round_number, COUNT(DISTINCT p.id) as solved_count
                    FROM rounds r
                    JOIN problems p ON r.id = p.round_id
                    JOIN user_progress up ON p.id = up.problem_id
                    WHERE up.user_id = ? AND up.is_correct = 1
                    GROUP BY r.round_number
                ''', (user_id,))
                
                progress = {row[0]: row[1] for row in c.fetchall()}
                total_solved = sum(progress.values())
                
                user_progress.append({
                    'id': user_id,
                    'progress': progress,
                    'total': total_solved
                })
            
            return render_template('admin.html', users=user_progress)
            
    except sqlite3.Error as e:
        flash('데이터베이스 오류가 발생했습니다.', 'error')
        return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)