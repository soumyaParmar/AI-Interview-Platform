import React, { useState } from 'react';

export interface SkillMap {
    must_have_tech: string[];
    nice_to_have_tech: string[];
    soft_skills: string[];
    experience_level: string;
    silent_observer_suggestions?: string[];
}

interface SkillReviewProps {
    initialSkills: SkillMap;
    onStartInterview: (finalSkills: SkillMap) => void;
}

const SkillReview: React.FC<SkillReviewProps> = ({ initialSkills, onStartInterview }) => {
    const [skills, setSkills] = useState<SkillMap>(initialSkills);
    const [newSkill, setNewSkill] = useState('');
    const [selectedCategory, setSelectedCategory] = useState<keyof SkillMap>('must_have_tech');

    const removeSkill = (category: keyof SkillMap, skillToRemove: string) => {
        if (category === 'experience_level') return;
        
        setSkills(prev => ({
            ...prev,
            [category]: (prev[category] as string[]).filter(s => s !== skillToRemove)
        }));
    };

    const addSkill = (e: React.FormEvent) => {
        e.preventDefault();
        if (!newSkill.trim() || selectedCategory === 'experience_level') return;

        setSkills(prev => ({
            ...prev,
            [selectedCategory]: [...(prev[selectedCategory] as string[]), newSkill.trim()]
        }));
        setNewSkill('');
    };

    const moveSkill = (skill: string, fromCategory: keyof SkillMap, toCategory: keyof SkillMap) => {
        if (fromCategory === 'experience_level' || toCategory === 'experience_level') return;

        setSkills(prev => ({
            ...prev,
            [fromCategory]: (prev[fromCategory] as string[]).filter(s => s !== skill),
            [toCategory]: [...(prev[toCategory] as string[]), skill]
        }));
    };

    const renderSkillPills = (category: keyof SkillMap, title: string, colorClass: string) => {
        const categorySkills = skills[category] as string[];
        if (!categorySkills || categorySkills.length === 0) return null;

        return (
            <div className="mb-6">
                <h4 className="text-sm font-semibold text-gray-700 mb-2">{title}</h4>
                <div className="flex flex-wrap gap-2">
                    {categorySkills.map(skill => (
                        <div key={skill} className={`flex items-center gap-1 px-3 py-1.5 rounded-full text-sm ${colorClass}`}>
                            <span>{skill}</span>
                            <div className="flex items-center gap-1 ml-2 border-l pl-2 border-black/10">
                                {category === 'nice_to_have_tech' && (
                                    <button 
                                        onClick={() => moveSkill(skill, 'nice_to_have_tech', 'must_have_tech')}
                                        className="hover:text-black font-bold"
                                        title="Move to Must Have"
                                    >↑</button>
                                )}
                                {category === 'must_have_tech' && (
                                    <button 
                                        onClick={() => moveSkill(skill, 'must_have_tech', 'nice_to_have_tech')}
                                        className="hover:text-black font-bold"
                                        title="Move to Nice to Have"
                                    >↓</button>
                                )}
                                <button 
                                    onClick={() => removeSkill(category, skill)}
                                    className="hover:text-red-700 font-bold ml-1"
                                    title="Remove"
                                >×</button>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        );
    };

    return (
        <div className="p-6 bg-white rounded-xl shadow-sm border mt-8 w-full max-w-3xl">
            <div className="flex justify-between items-center mb-6">
                <h3 className="text-xl font-bold text-gray-800">Review Interview Focus</h3>
                <span className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm font-semibold">
                    Level: {skills.experience_level}
                </span>
            </div>

            {skills.silent_observer_suggestions && skills.silent_observer_suggestions.length > 0 && (
                <div className="mb-6 p-4 bg-purple-50 rounded-lg border border-purple-100">
                    <h4 className="text-sm font-bold text-purple-800 mb-2 flex items-center gap-2">
                        ✨ Silent Observer Agent Suggestions
                    </h4>
                    <p className="text-xs text-purple-600 mb-3">
                        These skills weren't explicitly in the JD, but are highly standard for this role. Want to add them?
                    </p>
                    <div className="flex flex-wrap gap-2">
                        {skills.silent_observer_suggestions.map(skill => (
                            <button
                                key={skill}
                                onClick={() => moveSkill(skill, 'silent_observer_suggestions', 'nice_to_have_tech')}
                                className="px-3 py-1 bg-white text-purple-700 border border-purple-200 rounded-full text-sm hover:bg-purple-100 transition-colors flex items-center gap-1"
                            >
                                + {skill}
                            </button>
                        ))}
                    </div>
                </div>
            )}

            {renderSkillPills('must_have_tech', 'Must-Have Technical Skills', 'bg-blue-100 text-blue-800')}
            {renderSkillPills('nice_to_have_tech', 'Nice-to-Have Technical Skills', 'bg-green-100 text-green-800')}
            {renderSkillPills('soft_skills', 'Core Soft Skills', 'bg-orange-100 text-orange-800')}

            <form onSubmit={addSkill} className="flex gap-2 mt-6 pt-6 border-t">
                <select 
                    value={selectedCategory} 
                    onChange={(e) => setSelectedCategory(e.target.value as keyof SkillMap)}
                    className="border rounded-md px-3 py-2 text-sm bg-gray-50 outline-none focus:ring-2 focus:ring-blue-500"
                >
                    <option value="must_have_tech">Must-Have Tech</option>
                    <option value="nice_to_have_tech">Nice-to-Have Tech</option>
                    <option value="soft_skills">Soft Skills</option>
                </select>
                <input 
                    type="text" 
                    value={newSkill}
                    onChange={(e) => setNewSkill(e.target.value)}
                    placeholder="Add a new skill..."
                    className="flex-1 border rounded-md px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button type="submit" className="px-4 py-2 bg-gray-100 text-gray-700 rounded-md text-sm font-semibold hover:bg-gray-200 transition-colors">
                    Add
                </button>
            </form>

            <div className="mt-8 flex justify-end">
                <button 
                    onClick={() => onStartInterview(skills)}
                    className="px-6 py-3 bg-blue-600 text-white rounded-lg font-bold hover:bg-blue-700 transition-colors shadow-sm"
                >
                    Lock & Launch Agentic Interview
                </button>
            </div>
        </div>
    );
};

export default SkillReview;
