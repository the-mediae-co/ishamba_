import datetime

from django.utils.timezone import make_aware, get_current_timezone

from core.test.cases import TestCase

from ..utils.datetime import first_day_of_iso_week_date_year


class ISOWeekDateYearTestCase(TestCase):
    expected_values = [
        # Tuples of the form:
        #     ((y,m,d) date tuple, expected year, expected week, expected weekday)
        # Taken from http://en.wikipedia.org/wiki/ISO_week_date
        ((2005, 1, 1), 2004, 53, 6),  # Sat 1 Jan 2005
        ((2005, 1, 2), 2004, 53, 7),  # Sun 2 Jan 2005
        ((2005, 12, 31), 2005, 52, 6),  # Sat 31 Dec 2005
        ((2007, 1, 1), 2007, 1, 1),  # Mon 1 Jan 2007	Both years 2007 start with the same day.
        ((2007, 12, 30), 2007, 52, 7),  # Sun 30 Dec 2007
        ((2007, 12, 31), 2008, 1, 1),  # Mon 31 Dec 2007
        ((2008, 1, 1), 2008, 1, 2),  # Tue 1 Jan 2008	Gregorian year 2008 is a leap year. ISO year 2008 is 2 days shorter: 1 day longer at the start, 3 days shorter at the end.
        ((2008, 12, 28), 2008, 52, 7),  # Sun 28 Dec 2008	ISO year 2009 begins three days before the end of Gregorian 2008.
        ((2008, 12, 29), 2009, 1, 1),  # Mon 29 Dec 2008
        ((2008, 12, 30), 2009, 1, 2),  # Tue 30 Dec 2008
        ((2008, 12, 31), 2009, 1, 3),  # Wed 31 Dec 2008
        ((2009, 1, 1), 2009, 1, 4),  # Thu 1 Jan 2009
        ((2009, 12, 31), 2009, 53, 4),  # Thu 31 Dec 2009	ISO year 2009 has 53 weeks and ends three days into Gregorian year 2010.
        ((2010, 1, 1), 2009, 53, 5),  # Fri 1 Jan 2010
        ((2010, 1, 2), 2009, 53, 6),  # Sat 2 Jan 2010
        ((2010, 1, 3), 2009, 53, 7),  # Sun 3 Jan 2010
    ]

    def test_years_calculated_accurately(self):
        date = make_aware(
            datetime.datetime(2015, 3, 31, 6, 0, 0),
            get_current_timezone())

        for datetuple, year, week, weekday in self.expected_values:
            date = datetime.date(*datetuple)

            result = first_day_of_iso_week_date_year(date)

            calc_year, calc_week, calc_weekday = result.isocalendar()

            self.assertEqual(calc_year, calc_year)
            self.assertEqual(calc_week, 1)
            self.assertEqual(calc_weekday, 1)
