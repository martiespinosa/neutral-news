//
//  ContentView.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 12/17/24.
//

import SwiftUI

struct HomeView: View {
    @State private var vm = ViewModel()
    
    @State private var date: Date = Date.now
    
    var body: some View {
        NavigationStack {
            ScrollView {
                LazyVStack {
                    ForEach(vm.groupsOfNews, id: \.first!.id) { group in
                        if let firstNews = group.first {
                            NavigationLink(destination: NewsView(news: firstNews, relatedNews: group)) {
                                NewsImageView(news: firstNews)
                                    .padding(.vertical, 4)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
                .padding(.horizontal)
            }
            .refreshable {
                await vm.loadData()
            }
            .navigationTitle("Hoy")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) { filterMenu }
            }
        }
        .task {
            await vm.loadData()
        }
    }
    
    var filterMenu: some View {
        Menu {
            Menu("Media") {
                ForEach(Media.allCases, id: \.self) { media in
                    Button {
                        vm.filterByMedium(media)
                    } label: {
                        Label {
                            Text(media.pressMedia.name)
                        } icon: {
                            if vm.mediaFilter.contains(media) {
                                Image(systemName: "checkmark")
                            }
                        }
                    }

                }
            }
            Menu("Category") {
                ForEach(Category.allCases, id: \.self) { category in
                    Button {
                        vm.filterByCategory(category)
                    } label: {
                        Label {
                            Text(category.rawValue)
                        } icon: {
                            if vm.categoryFilter.contains(category) {
                                Image(systemName: "checkmark")
                            }
                        }
                    }
                }
            }
            
            if vm.isAnyFilterEnabled {
                Section {
                    Button("Clear Filters", role: .destructive) {
                        vm.mediaFilter.removeAll()
                        vm.categoryFilter.removeAll()
                        vm.filteredNews = vm.allNews
                    }
                }
            }
        } label: {
            Label("Filter", systemImage: vm.isAnyFilterEnabled ? "line.3.horizontal.decrease.circle.fill" : "line.3.horizontal.decrease.circle")
        }
    }
    
    func oneNewsForMedia() -> [News] {
        var oneNewsForMedia: [News] = []
        for mediaFilter in Media.allCases {
            if let firstNews = vm.filteredNews.filter({ $0.sourceMedium == mediaFilter }).first {
                oneNewsForMedia.append(firstNews)
            }
        }
        return oneNewsForMedia
    }
}

#Preview {
    HomeView()
}
