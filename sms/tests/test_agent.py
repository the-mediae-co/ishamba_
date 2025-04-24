import os
import unittest
from unittest.mock import patch

import pytest

from core.test.cases import TestCase
from sms.agent import (LLMException, SignupAiAgent, SignupInformation,
                       SignupInformationKenya, SignupInformationUganda)


@pytest.fixture
def mock_llm_response_kenya():
    return SignupInformationKenya(
        ward="Kisumu West",
        nearest_school="Kisumu Primary",
        county="Kisumu",
        name="John Doe",
        crops_livestock=["Maize", "Cattle"]
    )


@pytest.fixture
def mock_llm_response_uganda():
    return SignupInformationUganda(
        county="Lira",
        region="Northern",
        name="Jane Doe",
        crops_livestock=["Beans", "Goats"]
    )

class AgentTestCase(TestCase):

    # Test for Kenya Signup Information
    @unittest.skipUnless('INTEGRATION' in os.environ, "Test hits AWS Bedrock API and requires credentials")
    def test_invoke_kenya(self):
        agent = SignupAiAgent(country='Kenya')

        # Test the `invoke` method
        result = agent.invoke("My name is John Smith and I grow Maize and Cattle in Kisumu West near Kisumu Primary.")

        expected_result = SignupInformation(
            name="John Smith",
            crops_livestock=["Maize", "Cattle"],
            border1="Kisumu",
            border3="Kisumu West",
            nearest_school="Kisumu Primary"
        )

        assert result == expected_result
        # mock_llm.invoke.assert_called_once_with({'text': "I grow maize and cattle in Kisumu West near Kisumu Primary."})


    # Test for Uganda Signup Information
    def test_invoke_uganda(self):
        agent = SignupAiAgent(country='Uganda')

        # Test the `invoke` method
        result = agent.invoke("My name is Jane Doe and I grow beans and goats in Lira, Northern Uganda.")

        expected_result = SignupInformation(
            name="Jane Doe",
            crops_livestock=["beans", "goats"],
            border1="Northern",
            border3="Lira",
            nearest_school=None
        )

        assert result == expected_result
        # mock_llm.invoke.assert_called_once_with({'text': "I grow beans and goats in Lira, Northern Uganda."})


    # Test for Uganda Signup Information
    def test_invoke_zambia(self):

        agent = SignupAiAgent(country='Zambia')

        # Test the `invoke` method
        result = agent.invoke("My name is Chileya Kasuba and I grow beans and goats in Munali Constituency, Lusaka district, Zambia")

        expected_result = SignupInformation(
            name="Chileya Kasuba",
            crops_livestock=["beans", "goats"],
            border1="Lusaka",
            border3="Munali",
            nearest_school=None
        )

        assert result == expected_result


    # Test for failure in conversion
    @patch('sms.agent.get_llm')
    # def test_convert_country_specific_information_failure(self, mock_get_llm, mock_llm_response_kenya):
    def test_convert_country_specific_information_failure(self, mock_get_llm):
        agent = SignupAiAgent(country='Kenya')

        with pytest.raises(LLMException, match="Class conversion failed"):
            agent.convert_country_specific_information("Invalid Object")
