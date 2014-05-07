name := "Thunder"

version := "0.1.0"

scalaVersion := "2.10.3"

ivyXML := <dependency org="org.eclipse.jetty.orbit" name="javax.servlet" rev="2.5.0.v201103041518">
<artifact name="javax.servlet" type="orbit" ext="jar"/>
</dependency>

libraryDependencies += "org.apache.spark" %% "spark-core" % "0.9.0-incubating" % "provided"

libraryDependencies += "org.apache.spark" %% "spark-streaming" % "0.9.0-incubating" % "provided"

libraryDependencies += "org.apache.spark" % "spark-mllib_2.10" % "0.9.0-incubating" % "provided"

libraryDependencies += "org.scalatest" % "scalatest_2.10" % "2.0" % "test"

libraryDependencies += "io.spray" %% "spray-json" % "1.2.5"

libraryDependencies += "org.jblas" % "jblas" % "1.2.3"

libraryDependencies += "org.scalanlp" % "breeze_2.10" % "0.7"

libraryDependencies += "org.scalanlp" % "breeze-natives_2.10" % "0.7"

resolvers ++= Seq(
  "spray" at "http://repo.spray.io/",
  "Akka Repository" at "http://repo.akka.io/releases/",
  "Spray Repository" at "http://repo.spray.cc/",
  "Sonatype Snapshots" at "https://oss.sonatype.org/content/repositories/snapshots/",
  "Sonatype Releases" at "https://oss.sonatype.org/content/repositories/releases/"
)





