import unittest
from unittest.mock import patch
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.auth import get_current_user
from app.main import app
from app.models.user import User
from app.models.workout import Workout


class WorkoutApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.coach = User(email='coach@example.com', hashed_password='x', role='coach', vma=12)
        self.db.add(self.coach)
        self.db.flush()
        self.athlete = User(email='athlete@example.com', hashed_password='x', role='athlete', coach_id=self.coach.id, vma=16)
        self.db.add(self.athlete)
        self.db.commit()
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.coach
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()

    def test_history_pagination_and_access(self):
        start = datetime(2026, 1, 1)
        self.db.add_all([Workout(name=f'Séance {i}', workout_type='Libre', duration_minutes=30,
                                 difficulty_level=5, date=start + timedelta(days=i),
                                 athlete_id=self.athlete.id) for i in range(120)])
        self.db.commit()
        params = {'athlete_id': self.athlete.id, 'include_archived': 'true', 'limit': 100}
        first = self.client.get('/api/workouts', params=params)
        second = self.client.get('/api/workouts', params={**params, 'skip': 100})
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(len(first.json()), 100)
        self.assertEqual(len(second.json()), 20)
        self.assertFalse({w['id'] for w in first.json()} & {w['id'] for w in second.json()})
        filtered = self.client.get('/api/workouts', params={**params, 'date_from': '2026-01-02T00:00:00',
                                                            'date_to': '2026-01-04T00:00:00'})
        self.assertEqual(len(filtered.json()), 2)
        self.assertEqual(self.client.get('/api/workouts', params={'skip': -1}).status_code, 422)
        outsider = User(email='outsider@example.com', hashed_password='x', role='athlete')
        self.db.add(outsider)
        self.db.commit()
        self.assertEqual(self.client.get('/api/workouts', params={'athlete_id': outsider.id}).status_code, 403)

    def test_coach_cannot_access_unassigned_workout(self):
        outsider = User(email='other@example.com', hashed_password='x', role='athlete')
        self.db.add(outsider)
        self.db.flush()
        workout = Workout(name='Privé', workout_type='Libre', duration_minutes=30,
                          difficulty_level=5, date=datetime(2026, 1, 1), athlete_id=outsider.id)
        self.db.add(workout)
        self.db.commit()
        url = f'/api/workouts/{workout.id}'
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.patch(url, json={'name': 'modifié'}).status_code, 404)
        self.assertEqual(self.client.delete(url).status_code, 404)
        self.assertEqual(self.client.get(url + '/garmin').status_code, 404)
        self.assertEqual(self.client.post(url + '/validate', json={'perceived_difficulty': 5}).status_code, 404)

    def test_create_and_update_volumes(self):
        data = {'name': 'Test', 'workout_type': 'Fractionné', 'duration_minutes': 99,
                'distance_km': 99, 'difficulty_level': 5, 'date': '2026-12-01T10:00:00',
                'athlete_id': self.athlete.id, 'scheme': [{'repetitions': 2, 'intervals': [
                    {'duration': 5, 'pace_min': '5:00', 'pace_max': '5:00'},
                    {'distance': 1000, 'pace_min': '4:00', 'pace_max': '4:00'}]}]}
        response = self.client.post('/api/workouts', json=data)
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()['duration_minutes'], 18)
        self.assertEqual(response.json()['distance_km'], 4)
        response = self.client.patch('/api/workouts/' + str(response.json()['id']), json={
            'scheme': [{'repetitions': 3, 'intervals': [{'duration': 10, 'distance': 2000}]}]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['duration_minutes'], 30)
        self.assertEqual(response.json()['distance_km'], 6)
        self.assertEqual(response.json()['estimated_load'], 60)

    def test_plan_updates_only_target_athlete(self):
        data = {'race_name': '10 km', 'race_date': '2027-02-01T00:00:00', 'race_distance': 10,
                'start_date': '2026-12-07T00:00:00', 'sessions_per_week': 3,
                'goal_type': 'finish', 'training_days': [1, 3, 5], 'estimated_vma': 4,
                'athlete_id': self.athlete.id}
        with patch('app.api.plans.PlanGenerator.generate', return_value=[]):
            response = self.client.post('/api/plans', json=data)
        self.assertEqual(response.status_code, 200, response.text)
        self.db.refresh(self.athlete)
        self.db.refresh(self.coach)
        self.assertEqual(self.athlete.vma, 15)
        self.assertEqual(self.coach.vma, 12)

    def test_invalid_plan_does_not_change_vma(self):
        data = {'race_name': '10 km', 'race_date': '2027-02-01T00:00:00', 'race_distance': 10,
                'start_date': '2026-12-07T00:00:00', 'sessions_per_week': 3,
                'goal_type': 'finish', 'training_days': [1, 3, 5], 'estimated_vma': 0,
                'athlete_id': self.athlete.id}
        response = self.client.post('/api/plans', json=data)
        self.assertEqual(response.status_code, 422)
        self.db.refresh(self.athlete)
        self.assertEqual(self.athlete.vma, 16)

    def test_coach_plan_requires_explicit_target(self):
        data = {'race_name': '10 km', 'race_date': '2027-02-01T00:00:00', 'race_distance': 10,
                'start_date': '2026-12-07T00:00:00', 'sessions_per_week': 3,
                'goal_type': 'finish', 'training_days': [1, 3, 5], 'estimated_vma': 4}
        with patch('app.api.plans.PlanGenerator.generate', return_value=[]):
            response = self.client.post('/api/plans', json=data)
        self.assertEqual(response.status_code, 422, response.text)
        self.db.refresh(self.coach)
        self.assertEqual(self.coach.vma, 12)

    def test_manual_workout_and_unknown_distance(self):
        response = self.client.post('/api/workouts/manual', json={
            'workout_type': 'Libre', 'duration_minutes': 33, 'distance_km': 5,
            'date': '2026-12-01T10:00:00', 'athlete_id': self.athlete.id})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()['scheme'][0]['intervals'][0]['distance'], 5000)
        response = self.client.patch('/api/workouts/' + str(response.json()['id']), json={
            'scheme': [{'repetitions': 2, 'intervals': [{'duration': 7}]}]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['duration_minutes'], 14)
        self.assertIsNone(response.json()['distance_km'])

    def test_move_workout_date_and_errors(self):
        response = self.client.post('/api/workouts/manual', json={
            'workout_type': 'Libre', 'duration_minutes': 33, 'distance_km': 5,
            'date': '2026-12-01T10:00:00', 'athlete_id': self.athlete.id})
        self.assertEqual(response.status_code, 201, response.text)
        workout = response.json()
        url = '/api/workouts/' + str(workout['id'])
        response = self.client.patch(url, json={'date': '2026-12-05T10:00:00'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['date'], '2026-12-05T10:00:00')
        self.assertEqual(response.json()['athlete_id'], self.athlete.id)
        self.assertEqual(response.json()['duration_minutes'], workout['duration_minutes'])
        self.assertEqual(self.client.patch(url, json={'date': 'invalide'}).status_code, 422)
        self.assertEqual(self.client.patch('/api/workouts/999999', json={'date': '2026-12-05T10:00:00'}).status_code, 404)

    def test_plan_generation_failure_does_not_change_vma(self):
        data = {'race_name': '10 km', 'race_date': '2027-02-01T00:00:00', 'race_distance': 10,
                'start_date': '2026-12-07T00:00:00', 'sessions_per_week': 3,
                'goal_type': 'finish', 'training_days': [1, 3, 5], 'estimated_vma': 4,
                'athlete_id': self.athlete.id}
        with patch('app.api.plans.PlanGenerator.generate', side_effect=ValueError('erreur')):
            response = self.client.post('/api/plans', json=data)
        self.assertEqual(response.status_code, 422)
        self.db.refresh(self.athlete)
        self.assertEqual(self.athlete.vma, 16)

    def test_distance_without_pace_is_rejected(self):
        response = self.client.post('/api/workouts', json={
            'name': 'Test', 'workout_type': 'Fractionné', 'duration_minutes': 10,
            'difficulty_level': 5, 'date': '2026-12-01T10:00:00',
            'scheme': [{'repetitions': 1, 'intervals': [{'distance': 1000}]}]})
        self.assertEqual(response.status_code, 422, response.text)

    def test_real_plan_generation(self):
        response = self.client.post('/api/plans', json={
            'race_name': '10 km', 'race_date': '2027-02-01T00:00:00', 'race_distance': 10,
            'start_date': '2026-12-07T00:00:00', 'sessions_per_week': 3,
            'goal_type': 'maintien', 'training_days': [1, 3, 5], 'estimated_vma': 4,
            'athlete_id': self.athlete.id})
        self.assertEqual(response.status_code, 200, response.text)
        self.db.refresh(self.athlete)
        self.assertEqual(self.athlete.vma, 15)
        response = self.client.get('/api/workouts', params={'athlete_id': self.athlete.id})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertGreater(len(response.json()), 0)
        race = next(workout for workout in response.json() if workout['workout_type'] == 'Course')
        self.assertEqual(race['distance_km'], 10)


if __name__ == '__main__':
    unittest.main()