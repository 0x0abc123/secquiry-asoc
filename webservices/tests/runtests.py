# cd /path/to/src/secquiry/webservices
# python3 -m unittest tests/runtests.py
from unittest.mock import Mock
import json
import unittest
import app
import authhelpers
import cryptohelpers
import accesscontrol

## TestClient requires httpx
## pip install httpx
from fastapi.testclient import TestClient


class TestSecquiry(unittest.TestCase):

    def setUp(self):
        # Set up any necessary test fixtures
        self.client = TestClient(app.app)
        self.userdata_regular = {
            'uid': '0x123',
            authhelpers.AESGCMSECRETS_FIELD: cryptohelpers.generateAESGCMSecrets(),
            authhelpers.ADMIN_FIELD: False
        }
        self.baseNode = {
            'uid': '0x1000',
            'ty': 'Project',
            'l': 'P12345',
            'd': 'Test Project',
            'c': '{"custom":"data"}',
            'm': '2023-10-25T03:59:13.4260372Z',
            'e': '0x199',
            'a': 'r|o'
        }

    def cloneBaseNode(self):
        return json.loads(json.dumps(self.baseNode))

    def tearDown(self):
        # Clean up any resources created in the setUp method
        pass

    def test_get_debug_test(self):
        resp = self.client.get('/debug/test')
        result = resp.json()
        expected_output = {'result': 'hello'}
        self.assertEqual(result, expected_output)

    def test_get_debug_post(self):
        body = {"input": "some_value"}
        resp = self.client.post('/debug/test', data=json.dumps(body).encode('utf-8'))
        result = resp.json()
        expected_output = {'result': 'some_value'}
        self.assertEqual(result, expected_output)

    def test_accesscontrol_usercanaccessnode_can(self):
        node_canaccess = self.cloneBaseNode()        
        result = accesscontrol.CheckUserCanAccessNode(node_canaccess, self.userdata_regular, accesscontrol.PERM_READ)
        self.assertEqual(result, True)

    def test_accesscontrol_usercanaccessnode_cant(self):
        node_cantaccess = self.cloneBaseNode()
        node_cantaccess['a'] = ''    
        result = accesscontrol.CheckUserCanAccessNode(node_cantaccess, self.userdata_regular, accesscontrol.PERM_READ)
        self.assertEqual(result, False)

    def test_accesscontrol_encryptanddecrypt(self):
        node = self.cloneBaseNode()
        udata = self.userdata_regular
        es = accesscontrol.GetEncryptedStateString(node, udata)
        decryptedNode = accesscontrol.GetDecryptedState(es, udata)
        self.assertEqual(decryptedNode['uid'], node['uid'])
        self.assertEqual(decryptedNode['ty'], node['ty'])
        self.assertEqual(decryptedNode['e'], node['e'])
        self.assertEqual(decryptedNode['a'], node['a'])

    def test_accesscontrol_filterallowedpredicates(self):
        node_canaccess = self.cloneBaseNode()
        result = accesscontrol.FilterAllowedPredicates([node_canaccess], self.userdata_regular)
        self.assertEqual(len(result), 1)

        mappedproperties = [val for val in accesscontrol.allowedPredicatesAndMappings[node_canaccess['ty']].values()]
        for key in result[0]:
            self.assertEqual((key == 'es' or key in mappedproperties), True)

    #authhelpers.create_jwt('testuser','0x123')
"""
https://stackoverflow.com/questions/74831663/how-to-create-unit-tests-for-a-fastapi-endpoint-that-makes-request-to-another-en

from fastapi.testclient import TestClient

    @pytest.fixture(scope='module')
    def client() -> TestClient:
        return TestClient(app)

    def test_some_route(client):
        resp = client.get('/some/route', cookies={'session': create_session_cookie({'some': 'state'})})

    def test_get_data_with_mocked_db(self):
        # Create a mock object for DatabaseService
        mock_db_service = Mock(spec=DatabaseService)

        # Set the return value for fetch_data method of the mock
        mock_db_service.fetch_data.return_value = {'result': 'mocked_data'}

        # Create an instance of App with the mock object
        app_instance = App(mock_db_service)

        # Call the method you want to test
        result = app_instance.get_data('SELECT * FROM table')

        # Assert that the method returned the expected result
        self.assertEqual(result, {'result': 'mocked_data'})

        # Assert that fetch_data method of the mock was called with the correct argument
        mock_db_service.fetch_data.assert_called_once_with('SELECT * FROM table')
"""
