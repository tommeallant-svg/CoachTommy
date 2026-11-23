import unittest
from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai_auth import hash_ai_key
from app.api.ai_workouts import router
from app.database import Base, get_db
from app.models.ai_access import AIAccessKey
from app.models.plan import Plan
from app.models.user import User
from app.models.workout import Workout


class AIWorkoutTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine, expire_on_commit=False)()
        self.db.add_all([User(id=1, email='one@example.com', role='athlete'),
                         User(id=2, email='two@example.com', role='athlete'),
                         AIAccessKey(athlete_id=1, key_hash=hash_ai_key('ct_ai_test'))])
        self.db.commit()
        app = FastAPI()
        app.include_router(router, prefix='/api')
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)
        self.headers = {'Authorization': 'Bearer ct_ai_test'}
        self.data = {'name': 'Test', 'workout_type': 'Libre', 'duration_minutes': 10,
                     'difficulty_level': 5, 'date': '2026-12-01T10:00:00'}

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def test_auth_create_update_and_isolation(self):
        self.assertEqual(self.client.get('/api/ai/workouts').status_code, 401)
        response = self.client.post('/api/ai/workouts', headers=self.headers, json={**self.data,
            'scheme': [{'repetitions': 2, 'intervals': [{'duration': 5, 'distance': 1000}]}]})
        self.assertEqual(response.status_code, 201, response.text)
        workout = response.json()
        self.assertEqual((workout['athlete_id'], workout['duration_minutes'], workout['distance_km']), (1, 10, 2))
        self.assertFalse(workout['is_validated'])
        url = '/api/ai/workouts/' + str(workout['id'])
        response = self.client.patch(url, headers=self.headers, json={'scheme': [
            {'repetitions': 3, 'intervals': [{'duration': 10, 'distance': 2000}]}]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual((response.json()['duration_minutes'], response.json()['estimated_load']), (30, 60))
        other = Workout(name='Other', workout_type='Libre', duration_minutes=10, difficulty_level=5,
                        date=datetime(2026, 1, 1), athlete_id=2)
        self.db.add(other)
        self.db.commit()
        other_url = '/api/ai/workouts/' + str(other.id)
        self.assertEqual(self.client.get(other_url, headers=self.headers).status_code, 404)
        self.assertEqual(self.client.patch(other_url, headers=self.headers, json={'name': 'x'}).status_code, 404)
        self.assertEqual(self.client.delete(other_url, headers=self.headers).status_code, 405)
        self.assertEqual(self.client.post(url + '/validate', headers=self.headers, json={}).status_code, 404)
        self.assertEqual(self.client.delete(url, headers=self.headers).status_code, 405)
        self.assertEqual(self.client.get(url, headers=self.headers).status_code, 200)

    def test_forbidden_fields_and_invalid_volumes(self):
        created = self.client.post('/api/ai/workouts', headers=self.headers, json=self.data)
        self.assertEqual(created.status_code, 201, created.text)
        url = '/api/ai/workouts/' + str(created.json()['id'])
        for field in ('athlete_id', 'plan_id', 'is_validated', 'perceived_difficulty', 'athlete_comment', 'unknown'):
            self.assertEqual(self.client.post('/api/ai/workouts', headers=self.headers,
                                             json={**self.data, field: 1}).status_code, 422)
            self.assertEqual(self.client.patch(url, headers=self.headers, json={field: 1}).status_code, 422)
        for field in ('athlete_id', 'is_validated'):
            scheme = [{'repetitions': 1, 'intervals': [{'duration': 10, field: 1}]}]
            self.assertEqual(self.client.post('/api/ai/workouts', headers=self.headers,
                                             json={**self.data, 'scheme': scheme}).status_code, 422)
            self.assertEqual(self.client.patch(url, headers=self.headers, json={'scheme': scheme}).status_code, 422)
        response = self.client.post('/api/ai/workouts', headers=self.headers, json={**self.data,
            'scheme': [{'intervals': [{'distance': 1000}]}]})
        self.assertEqual(response.status_code, 422)

    def test_pagination_archive_and_unplanned(self):
        plan = Plan(athlete_id=1, is_archived=True)
        self.db.add(plan)
        self.db.flush()
        self.db.add_all([Workout(name='Unplanned', workout_type='Libre', duration_minutes=10, difficulty_level=5,
                                 date=datetime(2099, 1, 1), athlete_id=1),
                         Workout(name='Archived', workout_type='Libre', duration_minutes=10, difficulty_level=5,
                                 date=datetime(2099, 1, 2), athlete_id=1, plan_id=plan.id)])
        self.db.commit()
        url = '/api/ai/workouts'
        self.assertEqual([w['name'] for w in self.client.get(url, headers=self.headers).json()], ['Unplanned', 'Archived'])
        self.assertEqual([w['name'] for w in self.client.get(url, headers=self.headers,
                         params={'include_archived': 'false'}).json()], ['Unplanned'])
        self.assertEqual([w['name'] for w in self.client.get(url, headers=self.headers,
                         params={'skip': 1, 'limit': 1}).json()], ['Archived'])
        self.assertEqual(self.client.get(url, headers=self.headers, params={'skip': -1}).status_code, 422)
        self.assertEqual(self.client.get(url, headers=self.headers, params={
            'date_from': '2027-01-01T00:00:00', 'date_to': '2026-01-01T00:00:00'}).status_code, 422)


if __name__ == '__main__':
    unittest.main()