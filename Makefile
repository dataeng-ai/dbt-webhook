include version.txt

tag:
	git tag v$(PACKAGE_VERSION)
	git push origin v$(PACKAGE_VERSION)
