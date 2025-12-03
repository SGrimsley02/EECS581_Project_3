# EECS581_Project_3: Automated Scheduler

## Description

Auto Scheduler allows users to set scheduling preferences, import existing calendars, and create new events that align with their preferences which will be automatically scheduled, making weekly planning faster and easier.

## Requirements

* Python 3.x.x
* Django
* See requirements.txt for more details

## Getting Started

### Prerequisites

* PostgreSQL Account
    * Add env file with relevant database info to /auto_scheduler

### Steps

1. Clone/fork the repository
2. Set up prerequisites as stated above
3. Create a new environment with Python 3.x.x and install the libraries listed in requirements.txt:

```bash
pip install -r requirements.txt
```

4. Run the following command

```bash
# If first time running or changes made to models, run migrate:
# python3 /auto_scheduler/manage.py migrate

# Run development server
python3 /auto_scheduler/manage.py runserver
```

5. Navigate to the provided development server to enter the application.

## Contributors

* Kiara Grimsley
* Reeny Huang
* Audrey Pan
* Ella Nguyen
* Hart Nurnberg
* Lauren D'Souza

