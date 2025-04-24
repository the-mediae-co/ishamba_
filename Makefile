target_env := "ishamba"
hostname := $(shell uname -n)
update:
	@env | grep VIRTUAL_ENV | grep $(target_env) || (echo "virtualenv error: must set virtualenv to $(target_env)" && exit 1)
	@echo "virtualenv set correctly. Proceeding..."

	git pull
	pip install --upgrade pip
ifeq ($(hostname),portal.ishamba.com)
	pip install --upgrade -r requirements/production.txt
else
	pip install --upgrade -r requirements/development.txt
endif
	./manage.py check
	./manage.py migrate_schemas
	./manage.py collectstatic --noinput
ifeq ($(hostname),portal.ishamba.com)
	sudo systemctl restart celery
	sudo systemctl restart celery-beat
	touch /etc/uwsgi/sites/uwsgi.ini
endif
