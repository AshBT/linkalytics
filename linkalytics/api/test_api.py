import os
import json

from unittest   import TestCase, skipIf, skip
from subprocess import check_output
from base64     import b64encode
from flask      import current_app

from .. import create_app

from .. environment import cfg

def get_pid(name):
    return [
        int(i.split()[1]) for i in check_output(['ps', 'aux']).decode('utf-8').splitlines()
            if i.startswith(os.getlogin()) and name in i
    ]

class APITest(TestCase):

    def setUp(self):
        self.app = create_app(cfg)
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client(use_cookies=True)

    def tearDown(self):
        self.app_context.pop()

    def test_app_exists(self):
        self.assertFalse(current_app is None)

@skipIf(not(get_pid('disque-server')),  'Requires Disque Server Up')
@skipIf(not(get_pid('-m linkalytics')), 'No Workers listening on queue')
@skipIf(os.getenv('TRAVIS'),            'Not able to mock on CI')
class FullAPITest(TestCase):
    """
    Full API Test
    =============

    Tests each api endpoint as it goes through
    the round trip request-response cycle from

    Trip
    ----
    WSGI server <-> Disque <-> Worker

    This test will only run when these processes are available

    Required Processes
    ------------------
    * Disque Server (Port 7711)
    * Linkalytics Worker Processes
        - To Run: "python3 -m linkalytics"

    Optional Processes
    ------------------
    * Redis Cache Server   (Port 6379)
    * Tika Metadata Server (Port 9998)
    """

    def setUp(self):
        """
        Set Up Client Server for running test.

        Note:
        -----
        This will run your WSGI test server
        """
        self.app = create_app(cfg)
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client(use_cookies=True)

    def tearDown(self):
        self.app_context.pop()

    def get_api_headers(self, username, password):
        auth = b64encode(
            '{username}:{password}'.format(
                username=username,
                password=password,
            ).encode('utf-8')).decode('utf-8')
        return {
            'Authorization': 'Basic {auth}'.format(auth=auth),
        }

    def run_endpoint(self, endpoint, **data):
        headers = self.get_api_headers(cfg['api']['username'], cfg['api']['password'])
        response = self.client.post(
            '/{version}/{endpoint}'.format(version=cfg['api']['version'], endpoint=endpoint),
            content_type='application/json',
            headers=headers,
            data=json.dumps(data),
        )

        self.assertTrue(response.status_code == 200)

        return response

    @skipIf(not(get_pid('redis-server')), 'Redis Server not available')
    @skipIf(not(get_pid('tika-server')),  'Tika Server not available')
    def test_metadata(self):
        self.run_endpoint('metadata',
                          url="http://www.cic.gc.ca"
        )
    @skipIf(not(get_pid('redis-server')),  'Redis Server not available')
    def test_imgmeta(self):
        self.run_endpoint('imgmeta',
                          id="26609786"
        )
    def test_coincidence(self):
        self.run_endpoint('coincidence',
                          text="cali",
                          size=10,
        )
    def test_ngrams(self):
        self.run_endpoint('ngrams',
                          text='cali',
                          size='100',
                          ngrams=2
        )
    def test_search(self):
        self.run_endpoint('search',
                          search="cali",
                          size=100
        )
    def test_lsh(self):
        self.run_endpoint('lsh',
                          search='cali',
                          size=100
        )
    def test_phone(self):
        self.run_endpoint('enhance/phone',
                          text="1800295 408-291-2521"
        )
    def test_youtube(self):
        self.run_endpoint('enhance/youtube',
                          text='Have you seen this https://www.youtube.com/watch?t=3&v=ToyoBTiwZ6c'
        )
    def test_instagram(self):
        self.run_endpoint('enhance/instagram',
                          text='https://www.instagram.com/barackobama/'
        )
    def test_twitter(self):
        self.run_endpoint('enhance/twitter',
                          text='https://twitter.com/realDonaldTrump'
        )
    def test_merge(self):
        self.run_endpoint('factor/merge',
                          id="71046685",
                          factors=["phone", "email", "text", "title"]
        )
    def test_available(self):
        self.run_endpoint('factor/available',
                          id='71046685'
        )
    def test_constructor(self):
        self.run_endpoint('factor/constructor',
                          id="71046685",
                          factors=["phone", "email", "text", "title"]
        )

