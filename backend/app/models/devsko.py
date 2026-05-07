from sqlalchemy import BigInteger, Boolean, Column, DateTime, Float, ForeignKey, Integer, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import declarative_base


DevskoBase = declarative_base()


class User(DevskoBase):
    __tablename__ = "users"
    __table_args__ = {"schema": "public"}

    id = Column("userid", BigInteger, primary_key=True)
    name = Column(Text)
    email = Column(Text)


class UserInfo(DevskoBase):
    __tablename__ = "userinfo"
    __table_args__ = {"schema": "public"}

    id = Column("userinfoid", BigInteger, primary_key=True)
    userid = Column(BigInteger, ForeignKey("public.users.userid"))
    firstname = Column(Text)
    lastname = Column(Text)
    gender = Column(Text)
    city = Column(Text)
    countrycode = Column(Text)
    phonenumber = Column(BigInteger)


class UserResume(DevskoBase):
    __tablename__ = "userresumes"
    __table_args__ = {"schema": "public"}

    id = Column("userresumeid", BigInteger, primary_key=True)
    userid = Column(BigInteger, ForeignKey("public.users.userid"))
    resumetext = Column("llmresponse", Text) # Mapped to llmresponse where extracted text usually is
    resumedata = Column(JSONB)
    rawpdfdata = Column(Text)
    uploaddate = Column(DateTime(timezone=True))


class Skill(DevskoBase):
    __tablename__ = "skills"
    __table_args__ = {"schema": "public"}

    id = Column("skillid", Integer, primary_key=True)
    name = Column("skill", String)
    skilltypeid = Column("skilltypeid", Integer)
    description = Column("descr", Text)
    parentskillid = Column(BigInteger)


class AssessmentGroup(DevskoBase):
    __tablename__ = "assessmentgroups"
    __table_args__ = {"schema": "public"}

    id = Column("assessmentgroupid", Integer, primary_key=True)
    uuid = Column("assessmentgroupuuid", UUID(as_uuid=True), unique=True)
    title = Column(Text)
    description = Column(Text)
    companyid = Column(Integer)
    jobdescription = Column(JSONB)


class AssessmentGroupStep(DevskoBase):
    __tablename__ = "assessmentgroupsteps"
    __table_args__ = {"schema": "public"}

    id = Column("assessmentgroupstepid", Integer, primary_key=True)
    assessmentgroupid = Column(Integer, ForeignKey("public.assessmentgroups.assessmentgroupid"))
    assessmentid = Column(Integer)
    steporder = Column(Integer)


class Assessment(DevskoBase):
    __tablename__ = "assessments"
    __table_args__ = {"schema": "public"}

    id = Column("assessmentid", Integer, primary_key=True)
    title = Column("name", Text)
    description = Column(Text)
    companyid = Column(Integer)
    assessmenttype = Column("assessmenttypeid", Integer)


class AssessmentVersion(DevskoBase):
    __tablename__ = "assessmentversions"
    __table_args__ = {"schema": "public"}

    id = Column("assessmentversionid", BigInteger, primary_key=True)
    assessmentid = Column("assessmentid", Integer, ForeignKey("public.assessments.assessmentid"))
    versionnumber = Column("versionnumber", Integer)
    isactive = Column("islive", Boolean)


class AssessmentSection(DevskoBase):
    __tablename__ = "assessmentsections"
    __table_args__ = {"schema": "public"}

    id = Column("assessmentsectionid", Integer, primary_key=True)
    assessmentversionid = Column("assessmentversionid", Integer, ForeignKey("public.assessmentversions.assessmentversionid"))
    title = Column("name", Text)
    sectionorder = Column("orderid", Integer)


class AssessmentSectionSkill(DevskoBase):
    __tablename__ = "assessmentsectionsskills"
    __table_args__ = {"schema": "public"}

    id = Column("assessmentsectionskillsid", Integer, primary_key=True)
    assessmentsectionid = Column("assessmentsectionid", Integer, ForeignKey("public.assessmentsections.assessmentsectionid"))
    skillid = Column("skillid", Integer, ForeignKey("public.skills.skillid"))
    questionids = Column("questionids", JSONB)


class Question(DevskoBase):
    __tablename__ = "questions"
    __table_args__ = {"schema": "public"}

    id = Column("questionid", Integer, primary_key=True)
    questiontext = Column(Text)
    skillids = Column(ARRAY(Integer))
    canfollowup = Column(Boolean)
    maxfollowupq = Column(Integer)
    isaigenerated = Column(Boolean)
    metadata_json = Column("metadata", JSONB)


class UserAssessmentSession(DevskoBase):
    __tablename__ = "userassessmentsessions"
    __table_args__ = {"schema": "public"}

    # Marking both as relevant IDs, numeric one is often used for FKs
    userassessmentsessionid = Column(BigInteger, primary_key=True)
    id = Column("userassessmentsessionuuid", UUID(as_uuid=True), index=True)
    userid = Column(BigInteger, ForeignKey("public.users.userid"))

    assessmentgroupid = Column(Integer)
    assessmentid = Column(BigInteger, ForeignKey("public.assessments.assessmentid"))
    status = Column("assessmentstatusid", Integer)
    startedat = Column("starttime", DateTime(timezone=True))
    completedat = Column("endtime", DateTime(timezone=True))
    score = Column(Float)
    sessionstate = Column("sessionanalysisstatus", SmallInteger)
    sessionanalysis = Column("sessionanalysis", JSONB)


class UserAssessmentSessionResponse(DevskoBase):
    __tablename__ = "userassessmentsessionresponses"
    __table_args__ = {"schema": "public"}

    id = Column("userassessmentsessionresponseid", BigInteger, primary_key=True)
    userassessmentsessionid = Column(BigInteger, ForeignKey("public.userassessmentsessions.userassessmentsessionid"))
    questionid = Column(Integer, ForeignKey("public.questions.id"))
    dynamicquestionid = Column(BigInteger)
    response = Column(JSONB)
    skillid = Column(Integer, ForeignKey("public.skills.id"))
    responseanalysis = Column(JSONB)
    originatingresponseid = Column(BigInteger)
    followupdepth = Column(Integer)
    canfollowup = Column(Boolean)
    createdat = Column(DateTime(timezone=True))
    updatedat = Column(DateTime(timezone=True))


class DynamicQuestion(DevskoBase):
    __tablename__ = "dynamicquestions"
    __table_args__ = {"schema": "public"}

    id = Column("dynamicquestionid", BigInteger, primary_key=True)
    questiontext = Column(Text)
    expectedanswer = Column(Text)
    skillid = Column(Integer, ForeignKey("public.skills.id"))
    parentquestionid = Column(Integer, ForeignKey("public.questions.id"))
    originatingresponseid = Column(BigInteger)
    createdat = Column(DateTime(timezone=True))
