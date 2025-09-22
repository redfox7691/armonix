PKG_NAME := armonix
VERSION := 0.99.1
BUILD_DIR := build/deb
PKG_DIR := $(BUILD_DIR)/$(PKG_NAME)_$(VERSION)

.PHONY: deb clean_deb

deb: clean_deb
	mkdir -p $(PKG_DIR)/DEBIAN
	mkdir -p $(PKG_DIR)/usr/lib/$(PKG_NAME)
	mkdir -p $(PKG_DIR)/usr/bin
	mkdir -p $(PKG_DIR)/etc/$(PKG_NAME)
	mkdir -p $(PKG_DIR)/usr/share/$(PKG_NAME)/examples
	mkdir -p $(PKG_DIR)/usr/lib/systemd/system
	mkdir -p $(PKG_DIR)/usr/share/man/man1
	mkdir -p $(PKG_DIR)/var/lib/$(PKG_NAME)

	rsync -a --exclude 'build' --exclude '.git' --exclude '*.deb' ./ $(PKG_DIR)/usr/lib/$(PKG_NAME)/
	rm -rf $(PKG_DIR)/usr/lib/$(PKG_NAME)/build

	install -m755 scripts/armonix $(PKG_DIR)/usr/bin/armonix
	install -m644 armonix.conf $(PKG_DIR)/etc/$(PKG_NAME)/armonix.conf
	install -m644 keypad_config.json $(PKG_DIR)/etc/$(PKG_NAME)/keypad_config.json
	install -m644 launchkey_config.json $(PKG_DIR)/etc/$(PKG_NAME)/launchkey_config.json
	install -m644 armonix.conf $(PKG_DIR)/usr/share/$(PKG_NAME)/examples/armonix.conf
	install -m644 keypad_config.json $(PKG_DIR)/usr/share/$(PKG_NAME)/examples/keypad_config.json
	install -m644 launchkey_config.json $(PKG_DIR)/usr/share/$(PKG_NAME)/examples/launchkey_config.json

	install -m644 packaging/armonix.service $(PKG_DIR)/usr/lib/systemd/system/armonix.service
	gzip -9 -c man/armonix.1 > $(PKG_DIR)/usr/share/man/man1/armonix.1.gz

	sed "s/@VERSION@/$(VERSION)/" packaging/debian/control.in > $(PKG_DIR)/DEBIAN/control
	cp packaging/debian/conffiles $(PKG_DIR)/DEBIAN/conffiles
	install -m755 packaging/debian/postinst $(PKG_DIR)/DEBIAN/postinst
	install -m755 packaging/debian/prerm $(PKG_DIR)/DEBIAN/prerm
	install -m755 packaging/debian/postrm $(PKG_DIR)/DEBIAN/postrm

	dpkg-deb --build $(PKG_DIR) $(BUILD_DIR)/$(PKG_NAME)_$(VERSION).deb

clean_deb:
	rm -rf $(BUILD_DIR)
