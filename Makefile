PACKAGE = hkawstoolkit
PREFIX = $(DESTDIR)/usr
SYSCONFDIR=$(DESTDIR)/etc
DATADIR=$(PREFIX)/share
SYSTEMD_DIR=$(PREFIX)/lib/systemd/system
INSTALL = /bin/install -c
MKDIR = /bin/install -c -d
RM = rm -rf
TAR = /usr/bin/tar
PYTHON3 = $(shell which python3)
PIP3 = $(shell which pip3)
TMPDIR := $(shell mktemp -d)
CURRENT_DIR := $(shell pwd)


install:
	$(MKDIR) $(PREFIX)/bin
	$(MKDIR) $(SYSCONFDIR)/hkawstoolkit
	$(MKDIR) $(DATADIR)/hkawstoolkit

	$(PYTHON3) setup.py install

	$(INSTALL) -m 755 scripts/hk-aws-tool.py $(PREFIX)/bin
	$(INSTALL) -m 644 config/config.yaml $(SYSCONFDIR)/hkawstoolkit


uninstall:
	$(RM) $(PREFIX)/bin/hk-aws-tool.py
	$(RM) $(SYSCONFDIR)/hkawstoolkit
	$(RM) $(DATADIR)/hkawstoolkit

	$(PIP3) uninstall $(PACKAGE) -y --no-input
