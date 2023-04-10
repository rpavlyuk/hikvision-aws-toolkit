PACKAGE = hkawstoolkit
PREFIX ?= $(DESTDIR)/usr
SYSCONFDIR=$(DESTDIR)/etc
DATADIR=$(PREFIX)/share
SYSTEMD_DIR=$(PREFIX)/lib/systemd/system
CROND_DIR=$(SYSCONFDIR)/cron.d
WEBSVCUSER ?= rpavlyuk
ROOTUSER ?= root
S3BUCKET ?= my-video-surveillance
S3FSMOUNTFOLDER ?= /var/lib/cctv/storage
INSTALL = /bin/install -c
MKDIR = /bin/install -c -d
RM = rm -rf
TAR = /usr/bin/tar
COPY = cp --recursive -P
CHOWN = $(shell which chown)
PYTHON3 = $(shell which python3)
PIP3 = $(shell which pip3)
TMPDIR := $(shell mktemp -d)
CURRENT_DIR := $(shell pwd)
PERL := $(shell which perl)
REGEX = $(PERL) -pi -e
SYSTEMCTL := $(shell which systemctl)

install:
	$(MKDIR) $(PREFIX)/bin
	$(MKDIR) $(SYSCONFDIR)/hkawstoolkit
	$(MKDIR) $(DATADIR)/hkawstoolkit

	$(PYTHON3) setup.py install

	$(INSTALL) -m 755 scripts/hk-aws-tool.py $(PREFIX)/bin
	$(INSTALL) -m 644 config/config.yaml $(SYSCONFDIR)/hkawstoolkit

	$(INSTALL) -m 644 systemd/hk-aws-web.service $(SYSTEMD_DIR)/
	$(REGEX) 's/USERNAME/$(WEBSVCUSER)/gi' $(SYSTEMD_DIR)/hk-aws-web.service

	$(INSTALL) -m 644 cron.d/hk-aws-tool-collect $(CROND_DIR)
	$(REGEX) 's/USERNAME/$(WEBSVCUSER)/gi' $(CROND_DIR)/hk-aws-tool-collect

	$(COPY) web $(DATADIR)/hkawstoolkit
	$(CHOWN) -R $(WEBSVCUSER) $(DATADIR)/hkawstoolkit/web/cache

uninstall:
	$(RM) $(PREFIX)/bin/hk-aws-tool.py
	$(RM) $(SYSCONFDIR)/hkawstoolkit
	$(RM) $(DATADIR)/hkawstoolkit
	$(RM) $(SYSTEMD_DIR)/hk-aws-web.service

	$(PIP3) uninstall $(PACKAGE) -y --no-input

reload:
	$(SYSTEMCTL) daemon-reload
	$(SYSTEMCTL) restart hk-aws-web.service

s3fs-tool:
	$(INSTALL) -m 755 s3fs/s3fs-delcache.sh  $(PREFIX)/bin
	$(INSTALL) -m 755 s3fs/s3fs-hk-watchdog.sh  $(PREFIX)/bin
	$(REGEX) 's/S3BUCKET/$(S3BUCKET)/gi' $(PREFIX)/bin/s3fs-hk-watchdog.sh
	$(REGEX) 's/S3FSMOUNTFOLDER/$(S3FSMOUNTFOLDER)/gi' $(PREFIX)/bin/s3fs-hk-watchdog.sh
	$(INSTALL) -m 644 cron.d/s3fs-hk-watchdog $(CROND_DIR)
	$(REGEX) 's/USERNAME/$(ROOTUSER)/gi' $(CROND_DIR)/s3fs-hk-watchdog
	$(INSTALL) -m 644 cron.d/s3fs-cache-cleanup $(CROND_DIR)
	$(REGEX) 's/USERNAME/$(ROOTUSER)/gi' $(CROND_DIR)/s3fs-cache-cleanup
	$(REGEX) 's/S3BUCKET/$(S3BUCKET)/gi' $(CROND_DIR)/s3fs-cache-cleanup
