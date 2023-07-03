flatpak:
	
	mkdir -p /app
	cp -r export/* /app
	
	mkdir -p /app/share
	cp -r libre-menu-editor /app/share/libre-menu-editor

install:
	
	mkdir -p $(DESTDIR)/usr
	cp -r export/* $(DESTDIR)/usr
	
	mkdir -p $(DESTDIR)/usr/share
	cp -r libre-menu-editor $(DESTDIR)/usr/share/libre-menu-editor
