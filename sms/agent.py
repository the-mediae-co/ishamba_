import logging
from dataclasses import dataclass
from json import JSONDecodeError
from typing import List, Literal, Optional

from django.conf import settings

from langchain.output_parsers import PydanticOutputParser
from langchain_aws import ChatBedrock
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field

from world.models import Border

logger = logging.getLogger(__name__)


def get_llm():
    return ChatBedrock(
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        model_id=settings.LLM_MODEL_ID,
        model_kwargs=dict(temperature=settings.LLM_TEMPERATURE),
        region_name=settings.AWS_BEDROCK_REGION
    )


class SignupInformationKenya(BaseModel):
    ward: Optional[str] = Field(description='The name of the ward.')
    nearest_school: Optional[str] = Field(description='The name of the nearest School to the farmer.')
    county: Optional[str] = Field(description='The name of the county. Defaults to None.')
    name: Optional[str] = Field(description='The name of the customer')
    crops_livestock: List[str] = Field(description='A list of all crops and livestock that the customer farms.')

parser_kenya = PydanticOutputParser(pydantic_object=SignupInformationKenya)


class SignupInformationUganda(BaseModel):
    county: Optional[str] = Field(description='The name of the county.')
    region: Optional[str] = Field(description='The name of the region.')
    name: Optional[str] = Field(description='The name of the customer')
    crops_livestock: List[str] = Field(description='A list of all crops and livestock that the customer farms.')


parser_uganda = PydanticOutputParser(pydantic_object=SignupInformationUganda)



class SignupInformationZambia(BaseModel):
    province: Optional[str] = Field(description='The name of the province.')
    constituency: Optional[str] = Field(description='The name of the constituency.')
    name: Optional[str] = Field(description='The name of the customer')
    crops_livestock: List[str] = Field(description='A list of all crops and livestock that the customer farms.')


parser_zambia = PydanticOutputParser(pydantic_object=SignupInformationZambia)


parser_dict = {
    'Kenya': parser_kenya,
    'Uganda': parser_uganda,
    'Zambia': parser_zambia,
}

@dataclass
class SignupInformation:
    name: Optional[str]
    crops_livestock: List[str]
    border1: Optional[str]
    border3: Optional[str]
    nearest_school: Optional[str]


class SignupAiAgent:

    def get_prompt_dict(self):
        return {
            'Kenya': PromptTemplate(
                template="""
                You are an assistant designed to help farmers register for a farming assistance program.
                Your task is to collect the following information from the farmer: Name, Crops/Livestock, County, Ward and nearest School.
                Do not make anything up if categories are missing!
                If the message content is not related to a registration process, still follow the format instructions but ignore all fields!
                For locations try to use the provided county names to distinguish between counties and wards if the user does not specify which is which.

                Here is a complete list of all counties in Kenya:
                {kenya_counties}

                {format_instructions}

                Parse the following message received from the farmer:
                {text}
                """,
                input_variables=['text'],
                partial_variables={
                    'format_instructions': parser_kenya.get_format_instructions(),
                    'kenya_counties': ', '.join(Border.kenya_counties.values_list('name', flat=True)),
                }
            ),
            'Uganda': PromptTemplate(
                template="""
                You are an assistant designed to help farmers register for a farming assistance program.
                Your task is to collect the following information from the farmer: Name, Crops/Livestock, Region and County.
                Do not make anything up if categories are missing!
                If the message content is not related to a registration process, still follow the format instructions but ignore all fields!
                For locations try to use the provided region names to distinguish between regions and counties if the user does not specify which is which.

                Here is a complete list of all regions in Uganda:
                {uganda_regions}

                {format_instructions}

                Parse the following message received from the farmer:
                {text}
                """,
                input_variables=['text'],
                partial_variables={
                    'format_instructions': parser_uganda.get_format_instructions(),
                    'uganda_regions': ', '.join(Border.uganda_regions.values_list('name', flat=True)),
                }
            ),
            'Zambia': PromptTemplate(
                template="""
                You are an assistant designed to help farmers register for a farming assistance program.
                Your task is to collect the following information from the farmer: Name, Crops/Livestock, Province and Constituency.
                Do not make anything up if categories are missing!
                If the message content is not related to a registration process, still follow the format instructions but ignore all fields!
                For locations try to use the provided names to distinguish between provinces and constituencies if the user does not specify which is which.

                Here is a complete list of all regions in Uganda:
                {zambia_districts}

                {format_instructions}

                Parse the following message received from the farmer:
                {text}
                """,
                input_variables=['text'],
                partial_variables={
                    'format_instructions': parser_zambia.get_format_instructions(),
                    'zambia_districts': ', '.join(Border.zambia_districts.values_list('name', flat=True)),
                }
            ),
        }

    def __init__(self, country: Literal['Kenya', 'Uganda', 'Zambia']) -> None:
        self.prompt = self.get_prompt_dict()[country]
        self.parser = parser_dict[country]
        self.llm = get_llm()
        self.chain = self.prompt | self.llm | self.parser

    def invoke(self, message: str) -> SignupInformation:
        try:
            signup_information: SignupInformationKenya | SignupInformationUganda | SignupInformationZambia = self.chain.invoke({'text': message})
        except JSONDecodeError as e:
            logger.warning(e)
            raise LLMException()

        converted = self.convert_country_specific_information(signup_information)

        logger.info("AI Agent response: ", converted)

        return converted

    @staticmethod
    def convert_country_specific_information(country_specific_information: SignupInformationKenya | SignupInformationUganda | SignupInformationZambia) -> SignupInformation:
        match country_specific_information:
            case SignupInformationKenya(ward=ward, nearest_school=nearest_school, county=county, name=name, crops_livestock=crops_livestock):
                return SignupInformation(name=name, crops_livestock=crops_livestock, border1=county, border3=ward, nearest_school=nearest_school)
            case SignupInformationUganda(county=county, region=region, name=name, crops_livestock=crops_livestock):
                return SignupInformation(name=name, crops_livestock=crops_livestock, border1=region, border3=county, nearest_school=None)
            case SignupInformationZambia(constituency=constituency, province=province, name=name, crops_livestock=crops_livestock):
                return SignupInformation(name=name, crops_livestock=crops_livestock, border1=province, border3=constituency, nearest_school=None)
            case _: raise LLMException("Class conversion failed")


class LLMException(Exception):
    pass

@dataclass
class AiResponseValidation:
    is_complete: bool
    needs_human_intervention: bool = False
    error: Optional[str] = None
