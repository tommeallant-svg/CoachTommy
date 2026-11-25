import os
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.plans import router
from app.auth import create_access_token
from app.database import Base, get_db
from app.models import catalog, plan, user, workout


class MultisportPlanTest(unittest.TestCase):
    def setUp(self):
        self.secret = os.environ.get('JWT_SECRET_KEY')
        os.environ['JWT_SECRET_KEY'] = 'test-secret-with-at-least-32-characters'
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.Session() as db:
            db.add_all([user.User(id=1, email='athlete@example.com', role='athlete', coach_id=2, vma=15),
                        user.User(id=2, email='coach@example.com', role='coach')])
            db.commit()
        app = FastAPI()
        app.include_router(router, prefix='/api')
        def db_override():
            with self.Session() as db:
                yield db
        app.dependency_overrides[get_db] = db_override
        self.client = TestClient(app)
        self.headers = {'Authorization': 'Bearer ' + create_access_token({'sub': 'coach@example.com'})}
        self.payload = {'athlete_id': 1, 'race_name': 'Objectif', 'race_date': '2026-03-01T12:00:00',
                        'start_date': '2026-02-02T00:00:00', 'race_distance': 10,
                        'sessions_per_week': 2, 'goal_type': 'mixte',
                        'training_days': {'0': {'sport': 'swimming'}, '2': {'sport': 'strength'}}}

    def tearDown(self):
        self.client.close()
        self.engine.dispose()
        if self.secret is None:
            os.environ.pop('JWT_SECRET_KEY', None)
        else:
            os.environ['JWT_SECRET_KEY'] = self.secret

    def test_swim_strength_without_vma_and_roundtrip(self):
        response = self.client.post('/api/plans', json=self.payload, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNone(response.json()['estimated_vma'])
        self.assertEqual(response.json()['training_days']['0']['sport'], 'swimming')
        with self.Session() as db:
            self.assertEqual(db.get(user.User, 1).vma, 15)
            workouts = db.query(workout.Workout).all()
            self.assertEqual({w.sport for w in workouts}, {'swimming', 'strength'})
            self.assertTrue(all(w.scheme[0]['intervals'][0]['duration'] for w in workouts))
            strength = next(w for w in workouts if w.sport == 'strength')
            self.assertEqual(strength.scheme[0]['intervals'][0]['exercise_repetitions'], 10)
        self.assertEqual(self.client.get('/api/plans/current', params={'athlete_id': 1}, headers=self.headers).json()['training_days']['2']['sport'], 'strength')

    def test_mixed_and_invalid_requests(self):
        self.payload['training_days']['0'] = {'sport': 'running', 'category': 'Fractionné'}
        self.assertEqual(self.client.post('/api/plans', json=self.payload, headers=self.headers).status_code, 422)
        self.payload['estimated_vma'] = 5
        bad = dict(self.payload, training_days={'0': {'sport': 'rowing'}, '2': {'sport': 'strength'}})
        self.assertEqual(self.client.post('/api/plans', json=bad, headers=self.headers).status_code, 422)
        bad = dict(self.payload, sessions_per_week=3)
        self.assertEqual(self.client.post('/api/plans', json=bad, headers=self.headers).status_code, 422)
        bad = dict(self.payload, athlete_id=None)
        self.assertEqual(self.client.post('/api/plans', json=bad, headers=self.headers).status_code, 422)
        response = self.client.post('/api/plans', json=self.payload, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        with self.Session() as db:
            self.assertEqual(db.get(user.User, 1).vma, 12)
            self.assertEqual({w.sport for w in db.query(workout.Workout).all()}, {'running', 'strength'})

    def test_legacy_request(self):
        self.payload.update(training_days=[0, 2], estimated_vma=5)
        response = self.client.post('/api/plans', json=self.payload, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['training_days'], [0, 2])

    def test_cycling_without_ftp(self):
        self.payload['training_days']['0'] = {'sport': 'cycling'}
        response = self.client.post('/api/plans', json=self.payload, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        with self.Session() as db:
            cycling = db.query(workout.Workout).filter_by(sport='cycling').all()
            self.assertTrue(cycling)
            self.assertTrue(all(w.distance_km is None for w in cycling))